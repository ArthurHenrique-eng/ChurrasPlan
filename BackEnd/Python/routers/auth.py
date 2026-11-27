from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from models import ConsentimentoUsuario, Usuario
from schemas.auth import (
    AuthOut, ConsentimentosIniciaisIn, EsqueciSenhaIn, LoginIn, MensagemOut, RedefinirSenhaIn,
    RegistroUsuarioIn, UsuarioOut, VerificarEmailIn,
)
from services.auth import (
    consumir_token_usuario, criar_sessao, criar_token_usuario, enviar_email,
    hash_senha, hash_token, limpar_cookies, normalizar_email, revogar_sessao_atual,
    usuario_atual, usuario_atual_com_csrf, validar_email_simples, verificar_senha,
)
from services.seguranca import registrar_evento, verificar_limite

router = APIRouter(prefix="/api/auth", tags=["autenticacao"])


def _login_local():
    """Rotas de senha própria deixam de existir quando o login é do Neon Auth."""
    if settings.AUTH_PROVIDER == "neon":
        raise HTTPException(status_code=410, detail={
            "codigo": "LOGIN_NEON",
            "mensagem": "Cadastro, entrada e senha agora são feitos pelo login do ChurrasPlan em /api/auth/neon.",
        })


@router.post("/register", response_model=AuthOut, status_code=201)
def registrar(payload: RegistroUsuarioIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _login_local()
    email = normalizar_email(payload.email)
    chave_rate = verificar_limite(
        db, request, tipo="register", limite=settings.RATE_LIMIT_REGISTER_ATTEMPTS, adicional=email
    )
    if not payload.aceite_termos or not payload.aceite_privacidade:
        registrar_evento(db, tipo="register", chave_hash=chave_rate, sucesso=False)
        db.commit()
        raise HTTPException(status_code=422, detail="É necessário aceitar os Termos de Uso e a Política de Privacidade.")
    if not validar_email_simples(email):
        registrar_evento(db, tipo="register", chave_hash=chave_rate, sucesso=False)
        db.commit()
        raise HTTPException(status_code=422, detail="Informe um e-mail válido.")
    if db.query(Usuario).filter(Usuario.email == email).first():
        registrar_evento(db, tipo="register", chave_hash=chave_rate, sucesso=False)
        db.commit()
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.")
    try:
        usuario = Usuario(nome=payload.nome.strip(), email=email, senha_hash=hash_senha(payload.senha), papel="usuario")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.add(usuario)
    db.flush()
    from services.analytics import registrar_produto, atribuir_cadastro
    registrar_produto(db, "cadastro_criado", str(usuario.id), {"segmento": "b2c"})
    if payload.aceite_analytics:
        atribuir_cadastro(db, usuario, payload.referral_codigo)
    db.add_all([
        ConsentimentoUsuario(usuario_id=usuario.id, tipo="termos", versao=settings.TERMS_VERSION, concedido=True, origem="cadastro"),
        ConsentimentoUsuario(usuario_id=usuario.id, tipo="privacidade", versao=settings.PRIVACY_VERSION, concedido=True, origem="cadastro"),
        ConsentimentoUsuario(usuario_id=usuario.id, tipo="marketing", versao="v1", concedido=bool(payload.aceite_marketing), origem="cadastro"),
    ])
    registrar_evento(db, tipo="register", chave_hash=chave_rate, sucesso=True)
    token = criar_token_usuario(db, usuario, "verificar_email", 24 * 60)
    link = f"{settings.PUBLIC_APP_URL}/verificar-email.html?token={token}"
    enviar_email(email, "Verifique seu e-mail no ChurrasPlan", f"Olá, {usuario.nome}!\n\nVerifique seu e-mail: {link}\n", db=db)
    # Em produção, quando a verificação é obrigatória, não entregamos uma
    # sessão autenticada antes da confirmação do e-mail. Em desenvolvimento
    # isso pode ficar relaxado por configuração para facilitar testes locais.
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        criar_sessao(db, usuario, request, response)
    db.commit()
    return AuthOut(
        usuario=UsuarioOut.model_validate(usuario),
        mensagem=(
            "Conta criada. Verifique seu e-mail antes de entrar."
            if settings.REQUIRE_EMAIL_VERIFICATION
            else "Conta criada. Você já pode usar sua conta; verifique o e-mail quando possível."
        ),
        dev_verification_token=token if settings.APP_ENV != "production" else None,
    )


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _login_local()
    email = normalizar_email(payload.email)
    chave_rate = verificar_limite(
        db, request, tipo="login", limite=settings.RATE_LIMIT_LOGIN_ATTEMPTS, adicional=email
    )
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.ativo or not verificar_senha(payload.senha, usuario.senha_hash):
        registrar_evento(db, tipo="login", chave_hash=chave_rate, sucesso=False)
        db.commit()
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    if settings.REQUIRE_EMAIL_VERIFICATION and usuario.email_verificado_em is None:
        registrar_evento(db, tipo="login", chave_hash=chave_rate, sucesso=False)
        db.commit()
        raise HTTPException(status_code=403, detail="Verifique seu e-mail antes de entrar.")
    registrar_evento(db, tipo="login", chave_hash=chave_rate, sucesso=True)
    from services.auth import PASSWORD_HASHER
    if not usuario.senha_hash.startswith("$argon2id$") or PASSWORD_HASHER.check_needs_rehash(usuario.senha_hash):
        usuario.senha_hash = hash_senha(payload.senha)
    criar_sessao(db, usuario, request, response)
    db.commit()
    return AuthOut(usuario=UsuarioOut.model_validate(usuario), mensagem="Login realizado com sucesso.")


@router.post("/logout", response_model=MensagemOut)
def logout(
    request: Request,
    response: Response,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    revogar_sessao_atual(db, request)
    limpar_cookies(response)
    if settings.AUTH_PROVIDER == "neon":
        from services.neon_auth import apagar_cookies_neon, encerrar_no_neon
        encerrar_no_neon(request)
        apagar_cookies_neon(response, request)
    db.commit()
    return MensagemOut(mensagem="Sessão encerrada.")


@router.get("/me", response_model=UsuarioOut)
def me(request: Request, response: Response, usuario: Usuario = Depends(usuario_atual)):
    if settings.AUTH_PROVIDER == "neon":
        # Com o Neon Auth, o cookie de CSRF nasce aqui, ligado à sessão atual.
        from services.neon_auth import COOKIE_SESSAO, csrf_da_sessao
        csrf = csrf_da_sessao(hash_token(request.cookies.get(COOKIE_SESSAO, "")))
        response.set_cookie(
            settings.CSRF_COOKIE_NAME, csrf, httponly=False, secure=settings.COOKIE_SECURE,
            samesite="lax", max_age=settings.SESSION_DAYS * 86400, path="/",
        )
    return usuario


@router.post("/consentimentos", response_model=MensagemOut)
def consentimentos_iniciais(
    payload: ConsentimentosIniciaisIn,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    """Registra os aceites do cadastro de uma conta criada pelo Neon Auth."""
    if settings.AUTH_PROVIDER != "neon":
        raise HTTPException(status_code=404, detail="Recurso não encontrado.")
    if not payload.aceite_termos or not payload.aceite_privacidade:
        raise HTTPException(status_code=422, detail="É necessário aceitar os Termos de Uso e a Política de Privacidade.")
    existentes = {c.tipo for c in db.query(ConsentimentoUsuario).filter_by(usuario_id=usuario.id)}
    novos = [
        ConsentimentoUsuario(usuario_id=usuario.id, tipo=tipo, versao=versao, concedido=concedido, origem="cadastro")
        for tipo, versao, concedido in (
            ("termos", settings.TERMS_VERSION, True),
            ("privacidade", settings.PRIVACY_VERSION, True),
            ("marketing", "v1", bool(payload.aceite_marketing)),
        )
        if tipo not in existentes
    ]
    if novos and payload.aceite_analytics:
        from services.analytics import atribuir_cadastro
        atribuir_cadastro(db, usuario, payload.referral_codigo)
    db.add_all(novos)
    db.commit()
    return MensagemOut(mensagem="Cadastro concluído.")


@router.post("/verify-email", response_model=MensagemOut)
def verificar_email(payload: VerificarEmailIn, db: Session = Depends(get_db)):
    _login_local()
    usuario = consumir_token_usuario(db, payload.token, "verificar_email")
    if not usuario:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
    usuario.email_verificado_em = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return MensagemOut(mensagem="E-mail verificado com sucesso.")


@router.post("/forgot-password", response_model=MensagemOut)
def esqueci_senha(payload: EsqueciSenhaIn, request: Request, db: Session = Depends(get_db)):
    _login_local()
    email = normalizar_email(payload.email)
    chave_rate = verificar_limite(
        db, request, tipo="forgot_password", limite=settings.RATE_LIMIT_PUBLIC_ATTEMPTS, adicional=email
    )
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    dev_token = None
    if usuario and usuario.ativo:
        token = criar_token_usuario(db, usuario, "redefinir_senha", 60)
        link = f"{settings.PUBLIC_APP_URL}/redefinir-senha.html?token={token}"
        enviar_email(usuario.email, "Redefinição de senha — ChurrasPlan", f"Use este link para redefinir sua senha: {link}\n", db=db)
        dev_token = token if settings.APP_ENV != "production" else None
        db.commit()
    registrar_evento(db, tipo="forgot_password", chave_hash=chave_rate, sucesso=True)
    db.commit()
    return MensagemOut(mensagem="Se o e-mail existir, enviaremos as instruções de recuperação.", dev_token=dev_token)


@router.post("/reset-password", response_model=MensagemOut)
def redefinir_senha(payload: RedefinirSenhaIn, db: Session = Depends(get_db)):
    _login_local()
    usuario = consumir_token_usuario(db, payload.token, "redefinir_senha")
    if not usuario:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
    try:
        usuario.senha_hash = hash_senha(payload.nova_senha)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    for sessao in usuario.sessoes:
        sessao.revogada = True
    db.commit()
    return MensagemOut(mensagem="Senha redefinida. Faça login novamente.")
