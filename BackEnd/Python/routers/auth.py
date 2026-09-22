from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from models import ConsentimentoUsuario, Usuario
from schemas.auth import (
    AuthOut, EsqueciSenhaIn, LoginIn, MensagemOut, RedefinirSenhaIn,
    RegistroUsuarioIn, UsuarioOut, VerificarEmailIn,
)
from services.auth import (
    consumir_token_usuario, criar_sessao, criar_token_usuario, enviar_email,
    hash_senha, limpar_cookies, normalizar_email, revogar_sessao_atual,
    usuario_atual, usuario_atual_com_csrf, validar_email_simples, verificar_senha,
)
from services.seguranca import registrar_evento, verificar_limite

router = APIRouter(prefix="/api/auth", tags=["autenticacao"])


@router.post("/register", response_model=AuthOut, status_code=201)
def registrar(payload: RegistroUsuarioIn, request: Request, response: Response, db: Session = Depends(get_db)):
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
    db.add_all([
        ConsentimentoUsuario(usuario_id=usuario.id, tipo="termos", versao=settings.TERMS_VERSION, concedido=True, origem="cadastro"),
        ConsentimentoUsuario(usuario_id=usuario.id, tipo="privacidade", versao=settings.PRIVACY_VERSION, concedido=True, origem="cadastro"),
        ConsentimentoUsuario(usuario_id=usuario.id, tipo="marketing", versao="v1", concedido=bool(payload.aceite_marketing), origem="cadastro"),
    ])
    registrar_evento(db, tipo="register", chave_hash=chave_rate, sucesso=True)
    token = criar_token_usuario(db, usuario, "verificar_email", 24 * 60)
    link = f"{settings.PUBLIC_APP_URL}/verificar-email.html?token={token}"
    enviar_email(email, "Verifique seu e-mail no ChurrasPlan", f"Olá, {usuario.nome}!\n\nVerifique seu e-mail: {link}\n")
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
    criar_sessao(db, usuario, request, response)
    db.commit()
    return AuthOut(usuario=UsuarioOut.model_validate(usuario), mensagem="Login realizado com sucesso.")


@router.post("/logout", response_model=MensagemOut)
def logout(
    response: Response,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
):
    revogar_sessao_atual(db, session_cookie)
    limpar_cookies(response)
    db.commit()
    return MensagemOut(mensagem="Sessão encerrada.")


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_atual)):
    return usuario


@router.post("/verify-email", response_model=MensagemOut)
def verificar_email(payload: VerificarEmailIn, db: Session = Depends(get_db)):
    usuario = consumir_token_usuario(db, payload.token, "verificar_email")
    if not usuario:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
    usuario.email_verificado_em = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return MensagemOut(mensagem="E-mail verificado com sucesso.")


@router.post("/forgot-password", response_model=MensagemOut)
def esqueci_senha(payload: EsqueciSenhaIn, request: Request, db: Session = Depends(get_db)):
    email = normalizar_email(payload.email)
    chave_rate = verificar_limite(
        db, request, tipo="forgot_password", limite=settings.RATE_LIMIT_PUBLIC_ATTEMPTS, adicional=email
    )
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    dev_token = None
    if usuario and usuario.ativo:
        token = criar_token_usuario(db, usuario, "redefinir_senha", 60)
        link = f"{settings.PUBLIC_APP_URL}/redefinir-senha.html?token={token}"
        enviar_email(usuario.email, "Redefinição de senha — ChurrasPlan", f"Use este link para redefinir sua senha: {link}\n")
        dev_token = token if settings.APP_ENV != "production" else None
        db.commit()
    registrar_evento(db, tipo="forgot_password", chave_hash=chave_rate, sucesso=True)
    db.commit()
    return MensagemOut(mensagem="Se o e-mail existir, enviaremos as instruções de recuperação.", dev_token=dev_token)


@router.post("/reset-password", response_model=MensagemOut)
def redefinir_senha(payload: RedefinirSenhaIn, db: Session = Depends(get_db)):
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
