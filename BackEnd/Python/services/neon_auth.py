"""Login pelo Neon Auth (Better Auth gerenciado), com o FastAPI como proxy.

Ativo só com AUTH_PROVIDER=neon. O navegador fala com /api/auth/neon/*, que
repassa uma lista fechada de caminhos ao NEON_AUTH_BASE_URL. Assim o cookie de
sessão do Neon fica no domínio do ChurrasPlan (o Vercel já leva /api ao
Render), sem depender de cookie de terceiros, que o Safari bloqueia. É o mesmo
desenho do proxy do SDK oficial de Next.js (@neon/auth/next/server).

Em cada pedido, a API valida o cookie no `get-session` do Neon (com cache
curto) e mantém uma sessão espelho em `sessoes_usuario`: hash do cookie, CSRF
ligado à sessão e MFA verificado. Por isso as dependências `usuario_atual*`
continuam iguais para os routers. Papéis, organizações e o TOTP de admin
continuam no backend.

Regras de segurança:
- nenhum caminho de admin ou organização do Neon passa pelo proxy;
- POST exige Origin confiável (o Neon também confere);
- tokens são retirados do corpo e o JWT (`set-auth-jwt`) é descartado, então
  o JavaScript da página nunca vê credenciais;
- e-mail não verificado nunca vincula uma conta local existente;
- uma sessão espelho revogada não volta a valer, mesmo que o Neon ainda a aceite.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger("churrasplan.neon_auth")

PREFIXO_COOKIE = "__Secure-neon-auth."
COOKIE_SESSAO = PREFIXO_COOKIE + "session_token"
TIMEOUT_SEGUNDOS = 5.0
CORPO_MAXIMO_BYTES = 16 * 1024
TAMANHO_MAXIMO_COOKIE = 1024
SESSAO_RECENTE = timedelta(minutes=10)

# Caminho do Better Auth -> métodos aceitos. Tudo fora daqui recebe 404.
CAMINHOS_PERMITIDOS: dict[str, frozenset[str]] = {
    "sign-up/email": frozenset({"POST"}),
    "sign-in/email": frozenset({"POST"}),
    "sign-in/social": frozenset({"POST"}),
    "sign-out": frozenset({"POST"}),
    "get-session": frozenset({"GET"}),
    "send-verification-email": frozenset({"POST"}),
    "verify-email": frozenset({"GET"}),
    "email-otp/send-verification-otp": frozenset({"POST"}),
    "email-otp/check-verification-otp": frozenset({"POST"}),
    "email-otp/verify-email": frozenset({"POST"}),
    "request-password-reset": frozenset({"POST"}),
    "reset-password": frozenset({"POST"}),
    "forget-password/email-otp": frozenset({"POST"}),
    "email-otp/reset-password": frozenset({"POST"}),
    "change-password": frozenset({"POST"}),
    "update-user": frozenset({"POST"}),
    "list-sessions": frozenset({"GET"}),
    "revoke-session": frozenset({"POST"}),
    "revoke-other-sessions": frozenset({"POST"}),
    "revoke-sessions": frozenset({"POST"}),
}
# Links de e-mail com token no caminho (redirecionam ao callbackURL).
PREFIXOS_GET_PERMITIDOS = ("reset-password/",)
CHAVES_SECRETAS = frozenset({"token", "access_token", "refresh_token", "accessToken", "refreshToken", "idToken"})
CABECALHOS_REPASSADOS = ("user-agent", "content-type", "accept", "accept-language")


class NeonAuthIndisponivel(Exception):
    """O Neon Auth não respondeu ou respondeu algo inesperado."""


@dataclass(frozen=True)
class IdentidadeNeon:
    user_id: str
    email: str
    email_verificado: bool
    nome: str
    banido: bool
    sessao_criada_em: datetime
    sessao_expira_em: datetime


def neon_ativo() -> bool:
    return settings.AUTH_PROVIDER == "neon" and bool(settings.NEON_AUTH_BASE_URL)


def _agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _origem(url: str) -> str:
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}" if partes.scheme and partes.netloc else ""


def origens_confiaveis() -> set[str]:
    origens = {o.rstrip("/") for o in settings.CORS_ORIGINS if o and o != "*"}
    publica = _origem(settings.PUBLIC_APP_URL)
    if publica:
        origens.add(publica)
    return origens


def _cliente_sincrono() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_SEGUNDOS)


def _cliente_assincrono() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS)


def _cookies_neon(request: Request) -> str:
    return "; ".join(
        f"{nome}={valor}" for nome, valor in request.cookies.items()
        if nome.startswith(PREFIXO_COOKIE) and len(valor) <= TAMANHO_MAXIMO_COOKIE
    )


def _data(valor: object) -> datetime:
    if not isinstance(valor, str):
        raise NeonAuthIndisponivel("data ausente")
    try:
        data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as erro:
        raise NeonAuthIndisponivel("data inválida") from erro
    return data.astimezone(UTC).replace(tzinfo=None) if data.tzinfo else data


def interpretar_sessao(dados: object) -> IdentidadeNeon | None:
    """Converte a resposta de `get-session` (objeto ou null)."""
    if dados is None:
        return None
    if not isinstance(dados, dict):
        raise NeonAuthIndisponivel("resposta não é objeto")
    sessao, usuario = dados.get("session"), dados.get("user")
    if not isinstance(sessao, dict) or not isinstance(usuario, dict):
        return None
    user_id, email = usuario.get("id"), usuario.get("email")
    if not isinstance(user_id, str) or not 1 <= len(user_id) <= 36 or not isinstance(email, str) or "@" not in email:
        raise NeonAuthIndisponivel("usuário inválido")
    if sessao.get("userId") not in (None, user_id):
        raise NeonAuthIndisponivel("sessão de outro usuário")
    nome = usuario.get("name") if isinstance(usuario.get("name"), str) else ""
    return IdentidadeNeon(
        user_id=user_id,
        email=email.strip().lower(),
        email_verificado=usuario.get("emailVerified") is True,
        nome=nome.strip()[:120],
        banido=usuario.get("banned") is True,
        sessao_criada_em=_data(sessao.get("createdAt")),
        sessao_expira_em=_data(sessao.get("expiresAt")),
    )


class _Cache:
    """Cache em memória por processo: hash do cookie -> identidade (ou None)."""

    def __init__(self, limite: int = 10_000):
        self._dados: dict[str, tuple[float, IdentidadeNeon | None]] = {}
        self._trava = threading.Lock()
        self._limite = limite

    def obter(self, chave: str) -> tuple[bool, IdentidadeNeon | None]:
        with self._trava:
            item = self._dados.get(chave)
            if not item or item[0] <= time.monotonic():
                self._dados.pop(chave, None)
                return False, None
            return True, item[1]

    def guardar(self, chave: str, valor: IdentidadeNeon | None, segundos: float) -> None:
        with self._trava:
            if len(self._dados) >= self._limite:
                agora = time.monotonic()
                for k in [k for k, (expira, _) in self._dados.items() if expira <= agora]:
                    del self._dados[k]
                if len(self._dados) >= self._limite:
                    self._dados.clear()
            self._dados[chave] = (time.monotonic() + segundos, valor)

    def remover(self, chave: str) -> None:
        with self._trava:
            self._dados.pop(chave, None)

    def limpar(self) -> None:
        with self._trava:
            self._dados.clear()


cache_sessoes = _Cache()


def _chave(valor_cookie: str) -> str:
    return hashlib.sha256(valor_cookie.encode("utf-8")).hexdigest()


def validar_cookie(valor_cookie: str) -> IdentidadeNeon | None:
    """Pergunta ao Neon quem é o dono do cookie de sessão (com cache curto)."""
    chave = _chave(valor_cookie)
    achou, identidade = cache_sessoes.obter(chave)
    if achou:
        return identidade
    url = f"{settings.NEON_AUTH_BASE_URL}/get-session"
    try:
        with _cliente_sincrono() as cliente:
            resposta = cliente.get(url, headers={"cookie": f"{COOKIE_SESSAO}={valor_cookie}"})
    except httpx.HTTPError as erro:
        logger.warning("neon_auth: get-session falhou (%s)", type(erro).__name__)
        raise NeonAuthIndisponivel("Neon Auth indisponível") from erro
    if resposta.status_code >= 500 or resposta.status_code == 429:
        logger.warning("neon_auth: get-session respondeu HTTP %s", resposta.status_code)
        raise NeonAuthIndisponivel(f"get-session respondeu {resposta.status_code}")
    if resposta.status_code != 200:
        identidade = None
    else:
        try:
            identidade = interpretar_sessao(resposta.json())
        except ValueError as erro:
            raise NeonAuthIndisponivel("get-session não devolveu JSON") from erro
    if identidade and identidade.sessao_expira_em <= _agora():
        identidade = None
    cache_sessoes.guardar(chave, identidade, settings.NEON_AUTH_CACHE_SEGUNDOS if identidade else 10)
    return identidade


def csrf_da_sessao(token_hash: str) -> str:
    """CSRF assinado e ligado à sessão (double-submit assinado, OWASP)."""
    return hmac.new(settings.SECURITY_PEPPER.encode("utf-8"), f"csrf:{token_hash}".encode("utf-8"), hashlib.sha256).hexdigest()


def vincular_usuario(db: Session, identidade: IdentidadeNeon):
    """Encontra, vincula ou cria o usuário local da identidade do Neon."""
    from models import Usuario
    from services.auth import agora, normalizar_email

    usuario = db.query(Usuario).filter(Usuario.neon_auth_user_id == identidade.user_id).first()
    email = normalizar_email(identidade.email)
    if usuario:
        if identidade.email_verificado:
            usuario.email_verificado_em = usuario.email_verificado_em or agora()
            if usuario.email != email and not db.query(Usuario).filter(Usuario.email == email).first():
                usuario.email = email
        return usuario
    existente = db.query(Usuario).filter(Usuario.email == email).first()
    if existente:
        if existente.neon_auth_user_id or not identidade.email_verificado:
            # Só o dono do e-mail, comprovado pelo Neon, assume uma conta antiga.
            raise HTTPException(status_code=409, detail={
                "codigo": "EMAIL_NAO_VERIFICADO",
                "mensagem": "Confirme seu e-mail para acessar a conta que já existe com ele.",
            })
        existente.neon_auth_user_id = identidade.user_id
        existente.email_verificado_em = existente.email_verificado_em or agora()
        return existente
    usuario = Usuario(
        nome=identidade.nome or email.split("@", 1)[0][:120],
        email=email,
        senha_hash=None,
        papel="usuario",
        neon_auth_user_id=identidade.user_id,
        email_verificado_em=agora() if identidade.email_verificado else None,
    )
    db.add(usuario)
    db.flush()
    from services.analytics import registrar_produto
    registrar_produto(db, "cadastro_criado", str(usuario.id), {"segmento": "b2c"})
    return usuario


def sessao_espelho(db: Session, request: Request):
    """Sessão local equivalente à sessão do Neon do pedido, ou None."""
    from models import SessaoUsuario
    from services.auth import agora, hash_token

    valor = request.cookies.get(COOKIE_SESSAO)
    if not valor or len(valor) > TAMANHO_MAXIMO_COOKIE:
        return None
    token_hash = hash_token(valor)
    sessao = db.query(SessaoUsuario).filter(SessaoUsuario.token_hash == token_hash).first()
    if sessao and sessao.revogada:
        return None
    try:
        identidade = validar_cookie(valor)
    except NeonAuthIndisponivel:
        raise HTTPException(status_code=503, detail="Login temporariamente indisponível. Tente de novo em instantes.") from None
    if identidade is None or identidade.banido:
        return None
    if settings.REQUIRE_EMAIL_VERIFICATION and not identidade.email_verificado:
        return None
    if sessao is None:
        usuario = vincular_usuario(db, identidade)
        sessao = SessaoUsuario(
            usuario_id=usuario.id,
            token_hash=token_hash,
            csrf_hash=hash_token(csrf_da_sessao(token_hash)),
            expira_em=identidade.sessao_expira_em,
            user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        )
        try:
            with db.begin_nested():
                db.add(sessao)
                usuario.ultimo_login_em = agora()
        except IntegrityError:
            # Dois pedidos simultâneos da mesma sessão: vale a que gravou primeiro.
            sessao = db.query(SessaoUsuario).filter(SessaoUsuario.token_hash == token_hash).first()
            if sessao is None or sessao.revogada:
                return None
        db.commit()
    elif sessao.usuario.neon_auth_user_id != identidade.user_id:
        return None
    else:
        sessao.expira_em = identidade.sessao_expira_em
    if not sessao.usuario.ativo or sessao.expira_em <= agora():
        return None
    sessao.ultimo_uso_em = agora()
    return sessao


def esquecer_sessao(request: Request) -> None:
    valor = request.cookies.get(COOKIE_SESSAO)
    if valor:
        cache_sessoes.remover(_chave(valor))


def _post_servidor(request: Request, caminho: str, corpo: dict) -> httpx.Response:
    origem = _origem(settings.PUBLIC_APP_URL)
    with _cliente_sincrono() as cliente:
        return cliente.post(
            f"{settings.NEON_AUTH_BASE_URL}/{caminho}",
            json=corpo,
            headers={"cookie": _cookies_neon(request), "origin": origem, "content-type": "application/json"},
        )


def confirmar_senha(request: Request, senha: str) -> bool:
    """Reconfirma a senha da sessão atual no Neon (`verify-password`).

    Conta sem senha (só Google) confirma com uma sessão aberta há menos de 10
    minutos, como o Better Auth faz para ações sensíveis.
    """
    valor = request.cookies.get(COOKIE_SESSAO)
    if not valor or not senha or len(senha) > 1024:
        return False
    try:
        with _cliente_sincrono() as cliente:
            contas = cliente.get(f"{settings.NEON_AUTH_BASE_URL}/list-accounts",
                                 headers={"cookie": f"{COOKIE_SESSAO}={valor}"})
        provedores = {c.get("providerId") for c in contas.json() if isinstance(c, dict)} if contas.status_code == 200 else set()
        if contas.status_code == 200 and "credential" not in provedores:
            identidade = validar_cookie(valor)
            return bool(identidade and _agora() - identidade.sessao_criada_em <= SESSAO_RECENTE)
        resposta = _post_servidor(request, "verify-password", {"password": senha})
    except (httpx.HTTPError, ValueError, NeonAuthIndisponivel):
        raise HTTPException(status_code=503, detail="Não foi possível confirmar a senha agora. Tente de novo.") from None
    if resposta.status_code >= 500:
        raise HTTPException(status_code=503, detail="Não foi possível confirmar a senha agora. Tente de novo.")
    return resposta.status_code == 200


def encerrar_no_neon(request: Request, caminho: str = "sign-out") -> None:
    """Encerra sessões no Neon (sign-out, revoke-other-sessions ou revoke-sessions). Melhor esforço."""
    if not request.cookies.get(COOKIE_SESSAO):
        return
    try:
        resposta = _post_servidor(request, caminho, {})
        if resposta.status_code >= 400:
            logger.warning("neon_auth: %s respondeu HTTP %s", caminho, resposta.status_code)
    except httpx.HTTPError as erro:
        logger.warning("neon_auth: %s falhou (%s)", caminho, type(erro).__name__)
    finally:
        if caminho in {"sign-out", "revoke-sessions"}:
            esquecer_sessao(request)


def remover_usuario_neon(db: Session, neon_user_id: str | None) -> bool:
    """Apaga o usuário no schema neon_auth do mesmo banco (sessões e contas caem em cascata).

    O Neon gerenciado não libera `delete-user`; os dados de login ficam no
    próprio banco do projeto. Devolve False quando o schema não está neste banco
    (por exemplo, MySQL de compatibilidade), para a remoção ser feita no console.
    """
    if not neon_user_id or db.get_bind().dialect.name != "postgresql":
        return False
    from sqlalchemy import text
    existe = db.execute(text("SELECT to_regclass('neon_auth.\"user\"') IS NOT NULL")).scalar()
    if not existe:
        return False
    db.execute(text('DELETE FROM neon_auth."user" WHERE id = CAST(:id AS uuid)'), {"id": neon_user_id})
    return True


def apagar_cookies_neon(resposta: Response, request: Request) -> None:
    for nome in request.cookies:
        if nome.startswith(PREFIXO_COOKIE):
            resposta.delete_cookie(nome, path="/", secure=True, httponly=True, samesite="lax")


# ---------------------------------------------------------------- proxy ---

def _caminho_permitido(caminho: str, metodo: str) -> bool:
    metodos = CAMINHOS_PERMITIDOS.get(caminho)
    if metodos is not None:
        return metodo in metodos
    return metodo == "GET" and any(
        caminho.startswith(p) and "/" not in caminho[len(p):] and 0 < len(caminho) - len(p) <= 256
        for p in PREFIXOS_GET_PERMITIDOS
    )


def _reescrever_set_cookie(cabecalho: str) -> str | None:
    partes = [p.strip() for p in cabecalho.split(";") if p.strip()]
    if not partes or "=" not in partes[0]:
        return None
    nome = partes[0].split("=", 1)[0].strip()
    if not nome.startswith(PREFIXO_COOKIE):
        return None
    atributos = [partes[0], "Path=/", "Secure", "SameSite=Lax"]
    for atributo in partes[1:]:
        chave = atributo.split("=", 1)[0].strip().lower()
        if chave in {"max-age", "expires"}:
            atributos.append(atributo)
        elif chave == "httponly":
            atributos.append("HttpOnly")
    return "; ".join(atributos)


def _limpar_segredos(dados: object, profundidade: int = 0) -> object:
    if profundidade > 3:
        return dados
    if isinstance(dados, dict):
        return {k: _limpar_segredos(v, profundidade + 1) for k, v in dados.items() if k not in CHAVES_SECRETAS}
    if isinstance(dados, list):
        return [_limpar_segredos(v, profundidade + 1) for v in dados]
    return dados


def _destino_seguro(local: str) -> str | None:
    if local.startswith("/") and not local.startswith("//"):
        return local
    return local if _origem(local) in origens_confiaveis() else None


async def encaminhar(request: Request, caminho: str) -> Response:
    """Repassa um pedido do navegador ao Neon Auth e devolve a resposta saneada."""
    metodo = request.method.upper()
    if not neon_ativo():
        raise HTTPException(status_code=404, detail="Recurso não encontrado.")
    if not _caminho_permitido(caminho, metodo):
        raise HTTPException(status_code=404, detail="Recurso não encontrado.")
    origem = (request.headers.get("origin") or "").rstrip("/")
    confiaveis = origens_confiaveis()
    if metodo != "GET" and origem not in confiaveis:
        raise HTTPException(status_code=403, detail="Origem não autorizada.")
    if origem and origem not in confiaveis:
        raise HTTPException(status_code=403, detail="Origem não autorizada.")
    corpo = await request.body()
    if len(corpo) > CORPO_MAXIMO_BYTES:
        raise HTTPException(status_code=413, detail="Corpo da requisição excede o limite permitido.")

    cabecalhos = {k: v for k in CABECALHOS_REPASSADOS if (v := request.headers.get(k))}
    cabecalhos["origin"] = origem or _origem(settings.PUBLIC_APP_URL)
    cookies = _cookies_neon(request)
    if cookies:
        cabecalhos["cookie"] = cookies
    url = f"{settings.NEON_AUTH_BASE_URL}/{caminho}"
    try:
        async with _cliente_assincrono() as cliente:
            resposta = await cliente.request(metodo, url, params=request.query_params, content=corpo or None,
                                             headers=cabecalhos, follow_redirects=False)
    except httpx.HTTPError as erro:
        logger.warning("neon_auth: proxy %s falhou (%s)", caminho, type(erro).__name__)
        raise HTTPException(status_code=502, detail="Login temporariamente indisponível.") from None

    if caminho in {"sign-out", "revoke-sessions", "revoke-session", "change-password"}:
        esquecer_sessao(request)
    conteudo = resposta.content
    tipo = resposta.headers.get("content-type", "")
    if "application/json" in tipo and conteudo:
        try:
            conteudo = json.dumps(_limpar_segredos(json.loads(conteudo)), ensure_ascii=False).encode("utf-8")
        except ValueError:
            conteudo = b'{"erro":"resposta_invalida"}'
    saida = Response(content=conteudo, status_code=resposta.status_code)
    if tipo:
        saida.headers["content-type"] = tipo
    local = resposta.headers.get("location")
    if local and (destino := _destino_seguro(local)):
        saida.headers["location"] = destino
    for cabecalho in resposta.headers.get_list("set-cookie"):
        reescrito = _reescrever_set_cookie(cabecalho)
        if reescrito:
            saida.headers.append("set-cookie", reescrito)
    return saida
