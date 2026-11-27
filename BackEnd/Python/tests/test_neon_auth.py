"""Login pelo Neon Auth (AUTH_PROVIDER=neon) contra um Neon Auth simulado.

O Neon Auth falso responde como o Better Auth gerenciado: cookie
`__Secure-neon-auth.session_token=<token>.<assinatura>`, `get-session` devolve
objeto ou null, `verify-password` confere a senha da sessão. Nenhum teste fala
com a rede.
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pyotp
import pytest

from config import settings
from database.connection import get_db
from main import app
from models import ConsentimentoUsuario, SessaoUsuario, Usuario
from services import neon_auth
from services.auth import hash_token
from tests.test_fases_3_a_6 import cadastro_login, payload_novo
from tests.test_integracao_churrascos import client  # noqa: F401  (fixture)

BASE = "https://ep-teste.neonauth.exemplo/neondb/auth"
ORIGEM = "http://localhost:5500"
SENHA = "SenhaForte123"


def _iso(data: datetime) -> str:
    return data.astimezone(UTC).isoformat().replace("+00:00", "Z")


class NeonFalso:
    """Neon Auth em memória, chamado pelo httpx.MockTransport."""

    def __init__(self):
        self.usuarios: dict[str, dict] = {}
        self.sessoes: dict[str, dict] = {}
        self.pedidos: list[httpx.Request] = []
        self.fora_do_ar = False

    def criar(self, email, *, verificado=True, provedor="credential", criada_ha=timedelta(0), nome="Pessoa Teste"):
        uid = str(uuid.uuid4())
        self.usuarios[uid] = {"email": email, "nome": nome, "verificado": verificado, "provedor": provedor}
        return uid, self.nova_sessao(uid, criada_ha=criada_ha)

    def nova_sessao(self, uid, *, criada_ha=timedelta(0)):
        token = secrets.token_urlsafe(24)
        agora = datetime.now(UTC)
        self.sessoes[token] = {"uid": uid, "criada": agora - criada_ha, "expira": agora + timedelta(days=7)}
        return f"{token}.assinatura-falsa"

    def caminhos(self):
        return [p.url.path.removeprefix("/neondb/auth/") for p in self.pedidos]

    def _token(self, pedido: httpx.Request) -> str | None:
        for parte in pedido.headers.get("cookie", "").split(";"):
            nome, _, valor = parte.strip().partition("=")
            if nome == neon_auth.COOKIE_SESSAO:
                return valor.split(".", 1)[0]
        return None

    def _sessao_json(self, token):
        sessao = self.sessoes[token]
        usuario = self.usuarios[sessao["uid"]]
        return {
            "session": {"id": "s-" + token[:8], "token": token, "userId": sessao["uid"],
                        "createdAt": _iso(sessao["criada"]), "expiresAt": _iso(sessao["expira"])},
            "user": {"id": sessao["uid"], "email": usuario["email"], "name": usuario["nome"],
                     "emailVerified": usuario["verificado"], "banned": False},
        }

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.fora_do_ar:
            raise httpx.ConnectError("Neon fora do ar", request=pedido)
        caminho = pedido.url.path.removeprefix("/neondb/auth/")
        token = self._token(pedido)
        valida = token in self.sessoes
        if caminho == "get-session":
            if not valida:  # o Better Auth responde o JSON `null`
                return httpx.Response(200, content=b"null", headers={"content-type": "application/json"})
            return httpx.Response(200, json=self._sessao_json(token))
        if caminho == "list-accounts":
            if not valida:
                return httpx.Response(401, json={"code": "UNAUTHORIZED"})
            provedor = self.usuarios[self.sessoes[token]["uid"]]["provedor"]
            return httpx.Response(200, json=[{"id": "a1", "providerId": provedor, "accountId": "x"}])
        if caminho == "verify-password":
            corpo = json.loads(pedido.content or b"{}")
            if valida and corpo.get("password") == SENHA:
                return httpx.Response(200, json={"status": True})
            return httpx.Response(400, json={"code": "INVALID_PASSWORD"})
        if caminho in {"sign-out", "revoke-sessions"}:
            if valida:
                uid = self.sessoes[token]["uid"]
                for t in [t for t, s in self.sessoes.items() if s["uid"] == uid and (caminho == "revoke-sessions" or t == token)]:
                    del self.sessoes[t]
            return httpx.Response(200, json={"success": True})
        if caminho == "revoke-other-sessions":
            if valida:
                uid = self.sessoes[token]["uid"]
                for t in [t for t, s in self.sessoes.items() if s["uid"] == uid and t != token]:
                    del self.sessoes[t]
            return httpx.Response(200, json={"status": True})
        if caminho == "sign-up/email":
            corpo = json.loads(pedido.content)
            uid, valor = self.criar(corpo["email"], verificado=False, nome=corpo.get("name", ""))
            token_novo = valor.split(".", 1)[0]
            return httpx.Response(
                200,
                json={"token": token_novo, "user": {"id": uid, "email": corpo["email"], "emailVerified": False}},
                headers=[
                    ("set-cookie", f"{neon_auth.COOKIE_SESSAO}={valor}; Max-Age=604800; Path=/; HttpOnly; Secure; SameSite=None; Partitioned"),
                    ("set-cookie", "rastreio=1; Path=/; Domain=neonauth.exemplo"),
                    ("set-auth-jwt", "eyJhbGciOiJFZERTQSJ9.falso.falso"),
                ],
            )
        if caminho == "verify-email":
            destino = parse_qs(pedido.url.query.decode()).get("callbackURL", ["/"])[0]
            return httpx.Response(302, headers={"location": destino})
        return httpx.Response(404, json={"code": "NOT_FOUND"})


@pytest.fixture()
def neon(monkeypatch):
    falso = NeonFalso()
    transporte = httpx.MockTransport(falso)
    monkeypatch.setattr(neon_auth, "_cliente_sincrono", lambda: httpx.Client(transport=transporte))
    monkeypatch.setattr(neon_auth, "_cliente_assincrono", lambda: httpx.AsyncClient(transport=transporte))
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "neon")
    monkeypatch.setattr(settings, "NEON_AUTH_BASE_URL", BASE)
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", ORIGEM)
    monkeypatch.setattr(settings, "CORS_ORIGINS", [ORIGEM])
    neon_auth.cache_sessoes.limpar()
    yield falso
    neon_auth.cache_sessoes.limpar()


def _banco():
    return next(app.dependency_overrides[get_db]())


def _entrar(client, valor_cookie):
    client.cookies.clear()
    client.cookies.set(neon_auth.COOKIE_SESSAO, valor_cookie)
    resposta = client.get("/api/auth/me")
    return resposta


def _csrf(client):
    return {"X-CSRF-Token": client.cookies.get(settings.CSRF_COOKIE_NAME)}


def _aceitar(client):
    r = client.post("/api/auth/consentimentos", headers=_csrf(client),
                    json={"aceite_termos": True, "aceite_privacidade": True})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ proxy ---

def test_proxy_nao_existe_no_modo_local(client):
    assert settings.AUTH_PROVIDER == "local"
    r = client.get("/api/auth/neon/get-session")
    assert r.status_code == 404


def test_proxy_recusa_caminhos_e_metodos_fora_da_lista(client, neon):
    bloqueados = [
        ("GET", "admin/list-users"), ("POST", "admin/set-role"), ("POST", "organization/create"),
        ("POST", "delete-user"), ("POST", "get-session"), ("GET", "sign-in/email"),
        ("GET", "reset-password/abc/def"), ("GET", "list-accounts"), ("POST", "verify-password"),
    ]
    for metodo, caminho in bloqueados:
        r = client.request(metodo, f"/api/auth/neon/{caminho}", headers={"origin": ORIGEM})
        assert r.status_code == 404, (metodo, caminho, r.status_code)
    assert neon.pedidos == []


def test_proxy_exige_origem_confiavel(client, neon):
    corpo = {"email": "a@example.com", "password": SENHA}
    assert client.post("/api/auth/neon/sign-in/email", json=corpo).status_code == 403
    assert client.post("/api/auth/neon/sign-in/email", json=corpo,
                       headers={"origin": "https://malicioso.exemplo"}).status_code == 403
    assert client.get("/api/auth/neon/get-session", headers={"origin": "https://malicioso.exemplo"}).status_code == 403
    assert neon.pedidos == []


def test_proxy_saneia_cookies_tokens_e_jwt(client, neon):
    client.cookies.set("churrasplan_session", "segredo-local")
    client.cookies.set("__Secure-neon-auth.session_challenge", "desafio")
    r = client.post("/api/auth/neon/sign-up/email", headers={"origin": ORIGEM},
                    json={"email": "nova@example.com", "password": SENHA, "name": "Nova"})
    assert r.status_code == 200, r.text
    assert "token" not in r.json() and r.json()["user"]["email"] == "nova@example.com"
    assert "set-auth-jwt" not in r.headers

    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 1, cookies
    cookie = cookies[0]
    assert cookie.startswith(neon_auth.COOKIE_SESSAO + "=")
    for atributo in ("Path=/", "Secure", "SameSite=Lax", "HttpOnly", "Max-Age=604800"):
        assert atributo in cookie
    assert "Partitioned" not in cookie and "SameSite=None" not in cookie and "Domain" not in cookie

    enviado = neon.pedidos[-1]
    assert str(enviado.url) == f"{BASE}/sign-up/email"
    assert enviado.headers["origin"] == ORIGEM
    assert enviado.headers["cookie"] == "__Secure-neon-auth.session_challenge=desafio"


def test_proxy_get_session_nao_entrega_token_ao_navegador(client, neon):
    _, valor = neon.criar("leitura@example.com")
    client.cookies.set(neon_auth.COOKIE_SESSAO, valor)
    r = client.get("/api/auth/neon/get-session")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "leitura@example.com"
    assert "token" not in r.json()["session"]


def test_proxy_so_redireciona_para_o_proprio_site(client, neon):
    externo = client.get("/api/auth/neon/verify-email", follow_redirects=False,
                         params={"token": "t", "callbackURL": "https://malicioso.exemplo/roubo"})
    assert externo.status_code == 302 and "location" not in externo.headers
    interno = client.get("/api/auth/neon/verify-email", follow_redirects=False,
                         params={"token": "t", "callbackURL": f"{ORIGEM}/conta.html"})
    assert interno.headers["location"] == f"{ORIGEM}/conta.html"


def test_proxy_limita_corpo_e_trata_neon_fora_do_ar(client, neon):
    grande = client.post("/api/auth/neon/sign-in/email", headers={"origin": ORIGEM, "content-type": "application/json"},
                         content=b"x" * (neon_auth.CORPO_MAXIMO_BYTES + 1))
    assert grande.status_code == 413
    neon.fora_do_ar = True
    r = client.post("/api/auth/neon/sign-in/email", headers={"origin": ORIGEM},
                    json={"email": "a@example.com", "password": SENHA})
    assert r.status_code == 502


# ------------------------------------------------- sessão espelho e conta ---

def test_primeiro_acesso_cria_conta_local_vinculada(client, neon):
    uid, valor = neon.criar("Nova.Pessoa@Example.com", nome="Nova Pessoa")
    r = _entrar(client, valor)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "nova.pessoa@example.com"
    assert client.cookies.get(settings.CSRF_COOKIE_NAME) == neon_auth.csrf_da_sessao(hash_token(valor))

    db = _banco()
    usuario = db.query(Usuario).filter_by(email="nova.pessoa@example.com").one()
    assert usuario.neon_auth_user_id == uid
    assert usuario.senha_hash is None
    assert usuario.email_verificado_em is not None
    sessao = db.query(SessaoUsuario).filter_by(usuario_id=usuario.id).one()
    assert sessao.token_hash == hash_token(valor)

    assert client.get("/api/auth/me").status_code == 200
    assert neon.caminhos().count("get-session") == 1  # segunda chamada veio do cache


def test_sem_cookie_cookie_invalido_ou_grande_demais(client, neon):
    assert client.get("/api/auth/me").status_code == 401
    assert _entrar(client, "nao-existe.assinatura").status_code == 401
    assert _entrar(client, "x" * (neon_auth.TAMANHO_MAXIMO_COOKIE + 1)).status_code == 401


def test_email_nao_verificado_nao_entra_quando_verificacao_e_exigida(client, neon, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    _, valor = neon.criar("pendente@example.com", verificado=False)
    assert _entrar(client, valor).status_code == 401


def test_conta_antiga_e_vinculada_pelo_email_verificado(client, neon, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "local")
    antigo, h = cadastro_login(client, email="antiga@example.com")
    assert client.post("/api/churrascos", json=payload_novo(chave_cliente="conta-antiga-0001"), headers=h).status_code == 201
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "neon")

    uid, valor = neon.criar("antiga@example.com", verificado=True)
    r = _entrar(client, valor)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == antigo["usuario"]["id"]
    assert _banco().get(Usuario, antigo["usuario"]["id"]).neon_auth_user_id == uid
    lista = client.get("/api/churrascos/meus")
    assert lista.status_code == 200 and len(lista.json()) == 1
    nova = client.post("/api/churrascos", json=payload_novo(chave_cliente="conta-antiga-0002"), headers=_csrf(client))
    assert nova.status_code == 201, nova.text


def test_conta_antiga_nao_e_vinculada_sem_email_verificado(client, neon, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "local")
    antigo, _ = cadastro_login(client, email="alvo@example.com")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "neon")

    _, valor = neon.criar("alvo@example.com", verificado=False)
    r = _entrar(client, valor)
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "EMAIL_NAO_VERIFICADO"
    assert _banco().get(Usuario, antigo["usuario"]["id"]).neon_auth_user_id is None


def test_conta_nova_precisa_aceitar_termos_antes_de_usar_a_api(client, neon):
    _, valor = neon.criar("termos@example.com")
    assert _entrar(client, valor).status_code == 200
    bloqueado = client.post("/api/churrascos", json=payload_novo(), headers=_csrf(client))
    assert bloqueado.status_code == 403
    assert bloqueado.json()["detail"]["codigo"] == "CADASTRO_INCOMPLETO"

    assert client.post("/api/auth/consentimentos", json={"aceite_termos": True, "aceite_privacidade": True}).status_code == 403
    sem_privacidade = client.post("/api/auth/consentimentos", headers=_csrf(client),
                                  json={"aceite_termos": True, "aceite_privacidade": False})
    assert sem_privacidade.status_code == 422
    _aceitar(client)
    _aceitar(client)  # repetir não duplica
    tipos = sorted(c.tipo for c in _banco().query(ConsentimentoUsuario).all())
    assert tipos == ["marketing", "privacidade", "termos"]

    assert client.post("/api/churrascos", json=payload_novo(), headers=_csrf(client)).status_code == 201


def test_consentimentos_nao_existe_no_modo_local(client):
    _, h = cadastro_login(client, email="local@example.com")
    r = client.post("/api/auth/consentimentos", headers=h, json={"aceite_termos": True, "aceite_privacidade": True})
    assert r.status_code == 404


def test_mutacao_sem_csrf_e_recusada(client, neon):
    _, valor = neon.criar("csrf@example.com")
    _entrar(client, valor)
    _aceitar(client)
    assert client.post("/api/churrascos", json=payload_novo()).status_code == 403
    assert client.post("/api/churrascos", json=payload_novo(), headers={"X-CSRF-Token": "outro"}).status_code == 403


def test_logout_encerra_no_neon_e_a_sessao_espelho_nao_volta(client, neon):
    _, valor = neon.criar("sair@example.com")
    _entrar(client, valor)
    guardada = dict(neon.sessoes[valor.split(".", 1)[0]])
    r = client.post("/api/auth/logout", headers=_csrf(client))
    assert r.status_code == 200, r.text
    assert "sign-out" in neon.caminhos()
    assert any(c.startswith(neon_auth.COOKIE_SESSAO + "=") and "Max-Age=0" in c for c in r.headers.get_list("set-cookie"))

    # Mesmo que o Neon ainda aceitasse o cookie, a sessão revogada aqui não volta.
    neon.sessoes[valor.split(".", 1)[0]] = guardada
    neon_auth.cache_sessoes.limpar()
    assert _entrar(client, valor).status_code == 401


def test_rotas_de_senha_local_respondem_410(client, neon):
    chamadas = [
        ("/api/auth/register", {"nome": "Ana", "email": "ana@example.com", "senha": SENHA,
                                "aceite_termos": True, "aceite_privacidade": True}),
        ("/api/auth/login", {"email": "ana@example.com", "senha": SENHA}),
        ("/api/auth/forgot-password", {"email": "ana@example.com"}),
        ("/api/auth/reset-password", {"token": "t" * 32, "nova_senha": SENHA}),
        ("/api/auth/verify-email", {"token": "t" * 32}),
    ]
    for rota, corpo in chamadas:
        r = client.post(rota, json=corpo)
        assert r.status_code == 410, (rota, r.status_code, r.text)
        assert r.json()["detail"]["codigo"] == "LOGIN_NEON"


def test_neon_fora_do_ar_responde_503(client, neon):
    _, valor = neon.criar("instavel@example.com")
    neon.fora_do_ar = True
    assert _entrar(client, valor).status_code == 503


# ------------------------------------------- reautenticação, MFA e admin ---

def test_acao_sensivel_reconfirma_senha_no_neon(client, neon):
    _, valor = neon.criar("mfa@example.com")
    _entrar(client, valor)
    _aceitar(client)
    errada = client.post("/api/auth/mfa/configurar", json={"senha": "errada-123"}, headers=_csrf(client))
    assert errada.status_code == 401
    certa = client.post("/api/auth/mfa/configurar", json={"senha": SENHA}, headers=_csrf(client))
    assert certa.status_code == 200, certa.text
    pedido = next(p for p in reversed(neon.pedidos) if p.url.path.endswith("/verify-password"))
    assert pedido.headers["origin"] == ORIGEM
    assert pedido.headers["cookie"].startswith(neon_auth.COOKIE_SESSAO + "=")


def test_conta_so_google_reconfirma_com_login_recente(client, neon):
    _, recente = neon.criar("google-recente@example.com", provedor="google")
    _entrar(client, recente)
    _aceitar(client)
    ok = client.post("/api/auth/mfa/configurar", json={"senha": "qualquer"}, headers=_csrf(client))
    assert ok.status_code == 200, ok.text

    _, antiga = neon.criar("google-antigo@example.com", provedor="google", criada_ha=timedelta(minutes=30))
    _entrar(client, antiga)
    _aceitar(client)
    negado = client.post("/api/auth/mfa/configurar", json={"senha": "qualquer"}, headers=_csrf(client))
    assert negado.status_code == 401


def test_admin_continua_exigindo_mfa_do_backend(client, neon, monkeypatch):
    monkeypatch.setattr(settings, "MFA_REQUIRED_ADMIN", True)
    _, valor = neon.criar("admin@example.com")
    _, outra = neon.criar("admin2@example.com")
    _entrar(client, valor)
    _aceitar(client)
    db = _banco()
    usuario = db.query(Usuario).filter_by(email="admin@example.com").one()
    usuario.papel = "admin"
    db.commit()

    bloqueado = client.get("/api/admin/dashboard")
    assert bloqueado.status_code == 403
    assert bloqueado.json()["detail"]["codigo"] == "MFA_NECESSARIO"

    segredo = client.post("/api/auth/mfa/configurar", json={"senha": SENHA}, headers=_csrf(client)).json()["segredo"]
    ativado = client.post("/api/auth/mfa/ativar", json={"codigo": pyotp.TOTP(segredo).now()}, headers=_csrf(client))
    assert ativado.status_code == 200, ativado.text
    assert "revoke-other-sessions" in neon.caminhos()
    assert client.get("/api/admin/dashboard").status_code == 200
    assert outra  # a outra conta existe só para o Neon falso ter mais de uma sessão


def test_exclusao_de_conta_no_modo_neon(client, neon):
    _, valor = neon.criar("excluir@example.com")
    _entrar(client, valor)
    _aceitar(client)
    errada = client.request("DELETE", "/api/privacidade/minha-conta", headers=_csrf(client),
                            json={"senha": "errada-123", "confirmacao": "EXCLUIR"})
    assert errada.status_code == 403
    r = client.request("DELETE", "/api/privacidade/minha-conta", headers=_csrf(client),
                       json={"senha": SENHA, "confirmacao": "EXCLUIR"})
    assert r.status_code == 200, r.text
    assert _banco().query(Usuario).filter_by(email="excluir@example.com").first() is None
    assert any(c.startswith(neon_auth.COOKIE_SESSAO + "=") and "Max-Age=0" in c for c in r.headers.get_list("set-cookie"))


# ---------------------------------------------------------- configuração ---

def test_validacao_de_producao_confere_provedor_de_login():
    from config import validar_configuracao_producao
    base = dict(
        APP_ENV="production", COOKIE_SECURE=True, REQUIRE_EMAIL_VERIFICATION=False, SMTP_HOST=None,
        PUBLIC_APP_URL="https://churrasplan.exemplo", CORS_ORIGINS=["https://churrasplan.exemplo"],
        GEOAPIFY_ENABLED=False, GEOAPIFY_SERVER_API_KEY=None, GEOAPIFY_MAP_API_KEY=None,
        TRUSTED_HOSTS=["*"], SECURITY_PEPPER="curto", FORCE_HTTPS=False,
        DATABASE_URL="sqlite:///x.db", DATABASE_URL_OVERRIDE="sqlite:///x.db", DB_PASSWORD="",
    )
    with pytest.raises(RuntimeError) as invalido:
        validar_configuracao_producao(SimpleNamespace(**base, AUTH_PROVIDER="outro"))
    assert "AUTH_PROVIDER deve ser local ou neon" in str(invalido.value)
    with pytest.raises(RuntimeError) as sem_https:
        validar_configuracao_producao(SimpleNamespace(**base, AUTH_PROVIDER="neon", NEON_AUTH_BASE_URL="http://neon.exemplo"))
    assert "NEON_AUTH_BASE_URL deve usar HTTPS" in str(sem_https.value)
    with pytest.raises(RuntimeError) as certo:
        validar_configuracao_producao(SimpleNamespace(**base, AUTH_PROVIDER="neon", NEON_AUTH_BASE_URL=BASE))
    assert "AUTH_PROVIDER" not in str(certo.value) and "NEON_AUTH_BASE_URL" not in str(certo.value)


# -------------------------------------------------------------- unidades ---

def test_interpretar_sessao():
    agora = datetime.now(UTC)
    dados = {"session": {"userId": "u1", "createdAt": _iso(agora), "expiresAt": _iso(agora + timedelta(days=1))},
             "user": {"id": "u1", "email": " Pessoa@Example.COM ", "emailVerified": True, "name": "P"}}
    identidade = neon_auth.interpretar_sessao(dados)
    assert identidade.email == "pessoa@example.com" and identidade.email_verificado and not identidade.banido
    assert identidade.sessao_expira_em.tzinfo is None
    assert neon_auth.interpretar_sessao(None) is None
    assert neon_auth.interpretar_sessao({"session": None, "user": None}) is None
    with pytest.raises(neon_auth.NeonAuthIndisponivel):
        neon_auth.interpretar_sessao({**dados, "session": {**dados["session"], "userId": "outro"}})
    with pytest.raises(neon_auth.NeonAuthIndisponivel):
        neon_auth.interpretar_sessao([])


def test_reescrever_set_cookie():
    assert neon_auth._reescrever_set_cookie("outro=1; Path=/") is None
    assert neon_auth._reescrever_set_cookie("sem-valor") is None
    reescrito = neon_auth._reescrever_set_cookie(
        "__Secure-neon-auth.session_token=abc; Path=/api; Domain=neon.exemplo; Expires=Wed, 01 Jan 2031 00:00:00 GMT; "
        "SameSite=None; Partitioned; HttpOnly"
    )
    assert reescrito == ("__Secure-neon-auth.session_token=abc; Path=/; Secure; SameSite=Lax; "
                         "Expires=Wed, 01 Jan 2031 00:00:00 GMT; HttpOnly")


def test_caminho_permitido():
    assert neon_auth._caminho_permitido("sign-in/email", "POST")
    assert not neon_auth._caminho_permitido("sign-in/email", "GET")
    assert neon_auth._caminho_permitido("reset-password/abc123", "GET")
    assert not neon_auth._caminho_permitido("reset-password/abc/def", "GET")
    assert not neon_auth._caminho_permitido("reset-password/", "GET")
    assert not neon_auth._caminho_permitido("admin/impersonate-user", "POST")


def test_limpar_segredos():
    dados = {"token": "x", "user": {"id": "1", "accessToken": "y"}, "lista": [{"idToken": "z", "ok": 1}]}
    assert neon_auth._limpar_segredos(dados) == {"user": {"id": "1"}, "lista": [{"ok": 1}]}


def test_voltar_para_login_local_nao_quebra_conta_sem_senha(client, neon, monkeypatch):
    _, valor = neon.criar("rollback@example.com")
    assert _entrar(client, valor).status_code == 200
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "local")
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"email": "rollback@example.com", "senha": SENHA})
    assert r.status_code == 401
    assert client.post("/api/auth/forgot-password", json={"email": "rollback@example.com"}).status_code == 200
