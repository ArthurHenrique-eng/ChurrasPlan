"""Autenticação por sessão opaca em cookie HttpOnly.

- senha: PBKDF2-HMAC-SHA256 com salt aleatório;
- sessão: segredo aleatório enviado no cookie, apenas SHA-256 persistido;
- CSRF: double-submit cookie + hash vinculado à sessão para mutações autenticadas;
- tokens de e-mail/reset: opacos, uso único e expirados.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Iterable

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from models import SessaoUsuario, TokenUsuario, Usuario

PBKDF2_ITERATIONS = 600_000


def agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def validar_email_simples(email: str) -> bool:
    if len(email) > 160 or "@" not in email:
        return False
    local, dominio = email.rsplit("@", 1)
    return bool(local and dominio and "." in dominio and " " not in email)


def hash_senha(senha: str) -> str:
    if len(senha) < 10:
        raise ValueError("A senha deve ter pelo menos 10 caracteres.")
    if not any(c.isalpha() for c in senha) or not any(c.isdigit() for c in senha):
        raise ValueError("A senha deve combinar letras e números.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        algoritmo, iters, salt_b64, digest_b64 = senha_hash.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        esperado = base64.urlsafe_b64decode(digest_b64.encode())
        obtido = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, int(iters))
        return hmac.compare_digest(esperado, obtido)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def novo_segredo(bytes_: int = 32) -> str:
    return secrets.token_urlsafe(bytes_)


def criar_token_usuario(db: Session, usuario: Usuario, tipo: str, minutos: int) -> str:
    token = novo_segredo()
    db.add(TokenUsuario(
        usuario_id=usuario.id,
        tipo=tipo,
        token_hash=hash_token(token),
        expira_em=agora() + timedelta(minutes=minutos),
    ))
    db.flush()
    return token


def consumir_token_usuario(db: Session, token: str, tipo: str) -> Usuario | None:
    registro = (
        db.query(TokenUsuario)
        .filter(
            TokenUsuario.token_hash == hash_token(token),
            TokenUsuario.tipo == tipo,
            TokenUsuario.usado_em.is_(None),
            TokenUsuario.expira_em > agora(),
        )
        .first()
    )
    if not registro:
        return None
    registro.usado_em = agora()
    db.flush()
    return registro.usuario


def enviar_email(destino: str, assunto: str, corpo: str) -> bool:
    if not settings.SMTP_HOST:
        return False
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.SMTP_FROM
    msg["To"] = destino
    msg.set_content(corpo)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_TLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
        smtp.send_message(msg)
    return True


def _hash_ip_sessao(request: Request) -> str | None:
    host = request.client.host if request.client else None
    if not host:
        return None
    return hmac.new(settings.SECURITY_PEPPER.encode("utf-8"), host.encode("utf-8"), hashlib.sha256).hexdigest()


def criar_sessao(db: Session, usuario: Usuario, request: Request, response: Response) -> None:
    segredo = novo_segredo()
    csrf = novo_segredo(24)
    sessao = SessaoUsuario(
        usuario_id=usuario.id,
        token_hash=hash_token(segredo),
        csrf_hash=hash_token(csrf),
        expira_em=agora() + timedelta(days=settings.SESSION_DAYS),
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        ip_hash=_hash_ip_sessao(request),
    )
    db.add(sessao)
    usuario.ultimo_login_em = agora()
    db.flush()
    response.set_cookie(
        settings.SESSION_COOKIE_NAME, segredo,
        httponly=True, secure=settings.COOKIE_SECURE, samesite="lax",
        max_age=settings.SESSION_DAYS * 86400, path="/",
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME, csrf,
        httponly=False, secure=settings.COOKIE_SECURE, samesite="lax",
        max_age=settings.SESSION_DAYS * 86400, path="/",
    )


def limpar_cookies(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


def _buscar_sessao(db: Session, segredo: str | None) -> SessaoUsuario | None:
    if not segredo:
        return None
    sessao = db.query(SessaoUsuario).filter(SessaoUsuario.token_hash == hash_token(segredo)).first()
    if not sessao or sessao.revogada or sessao.expira_em <= agora() or not sessao.usuario.ativo:
        return None
    if settings.REQUIRE_EMAIL_VERIFICATION and sessao.usuario.email_verificado_em is None:
        return None
    sessao.ultimo_uso_em = agora()
    return sessao


def usuario_opcional(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
) -> Usuario | None:
    sessao = _buscar_sessao(db, session_cookie)
    return sessao.usuario if sessao else None


def usuario_atual(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
) -> Usuario:
    sessao = _buscar_sessao(db, session_cookie)
    if not sessao:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Faça login para acessar este recurso.")
    return sessao.usuario


def usuario_atual_com_csrf(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    csrf_cookie: str | None = Cookie(default=None, alias=settings.CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> Usuario:
    sessao = _buscar_sessao(db, session_cookie)
    if not sessao:
        raise HTTPException(status_code=401, detail="Faça login para acessar este recurso.")
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="Token CSRF ausente ou inválido.")
    if not hmac.compare_digest(sessao.csrf_hash, hash_token(csrf_header)):
        raise HTTPException(status_code=403, detail="Token CSRF não pertence à sessão atual.")
    return sessao.usuario



def usuario_opcional_com_csrf(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    csrf_cookie: str | None = Cookie(default=None, alias=settings.CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> Usuario | None:
    if not session_cookie:
        return None
    sessao = _buscar_sessao(db, session_cookie)
    if not sessao:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="Token CSRF ausente ou inválido.")
    if not hmac.compare_digest(sessao.csrf_hash, hash_token(csrf_header)):
        raise HTTPException(status_code=403, detail="Token CSRF não pertence à sessão atual.")
    return sessao.usuario

def exigir_papeis(*papeis: str, mutacao: bool = False):
    dependencia = usuario_atual_com_csrf if mutacao else usuario_atual

    def _dep(usuario: Usuario = Depends(dependencia)) -> Usuario:
        if usuario.papel not in papeis:
            raise HTTPException(status_code=403, detail="Sua conta não possui permissão para este recurso.")
        return usuario

    return _dep


def revogar_sessao_atual(db: Session, segredo: str | None) -> None:
    sessao = _buscar_sessao(db, segredo)
    if sessao:
        sessao.revogada = True
        db.flush()
