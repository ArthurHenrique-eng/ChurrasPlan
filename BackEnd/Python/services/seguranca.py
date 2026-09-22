from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from config import settings
from models import AuditoriaAdmin, EventoSeguranca, Usuario
from services.auth import agora


def _ip_cliente(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "desconhecido"


def chave_rate_limit(request: Request, escopo: str, adicional: str | None = None) -> str:
    ua = (request.headers.get("user-agent") or "")[:120]
    base = f"{escopo}|{_ip_cliente(request)}|{ua}|{adicional or ''}"
    return hmac.new(
        settings.SECURITY_PEPPER.encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verificar_limite(
    db: Session,
    request: Request,
    *,
    tipo: str,
    limite: int,
    adicional: str | None = None,
    janela_segundos: int | None = None,
) -> str:
    """Valida um limite persistido. Retorna a chave hash para registrar a tentativa."""
    if not settings.RATE_LIMIT_ENABLED:
        return chave_rate_limit(request, tipo, adicional)
    janela = janela_segundos or settings.RATE_LIMIT_WINDOW_SECONDS
    chave = chave_rate_limit(request, tipo, adicional)
    desde = agora() - timedelta(seconds=janela)
    total = (
        db.query(EventoSeguranca)
        .filter(
            EventoSeguranca.tipo == tipo,
            EventoSeguranca.chave_hash == chave,
            EventoSeguranca.criado_em >= desde,
        )
        .count()
    )
    if total >= limite:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente.",
            headers={"Retry-After": str(janela)},
        )
    return chave


def registrar_evento(db: Session, *, tipo: str, chave_hash: str, sucesso: bool) -> None:
    db.add(EventoSeguranca(tipo=tipo, chave_hash=chave_hash, sucesso=sucesso))
    db.flush()


def limpar_eventos_antigos(db: Session) -> int:
    limite = agora() - timedelta(days=settings.SECURITY_EVENT_RETENTION_DAYS)
    removidos = db.query(EventoSeguranca).filter(EventoSeguranca.criado_em < limite).delete(synchronize_session=False)
    db.flush()
    return int(removidos or 0)


def registrar_auditoria(
    db: Session,
    admin: Usuario,
    *,
    acao: str,
    entidade: str,
    entidade_id: str | int | None = None,
    detalhes: dict | None = None,
) -> None:
    db.add(
        AuditoriaAdmin(
            admin_usuario_id=admin.id,
            acao=acao,
            entidade=entidade,
            entidade_id=str(entidade_id) if entidade_id is not None else None,
            detalhes=detalhes or None,
        )
    )
    db.flush()
