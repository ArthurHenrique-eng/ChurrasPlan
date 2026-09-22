from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class EventoSeguranca(Base):
    """Evento mínimo para rate limiting/auditoria defensiva.

    `chave_hash` é um HMAC de um identificador efêmero (ex.: IP + rota), nunca
    o IP puro. O registro expira por política de retenção operacional.
    """

    __tablename__ = "eventos_seguranca"
    __table_args__ = (
        Index("ix_eventos_seguranca_tipo_chave_criado", "tipo", "chave_hash", "criado_em"),
    )

    id = Column(Integer, primary_key=True)
    tipo = Column(String(40), nullable=False, index=True)
    chave_hash = Column(String(64), nullable=False, index=True)
    sucesso = Column(Boolean, nullable=False, default=False, server_default="0")
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class AuditoriaAdmin(Base):
    """Trilha de mudanças privilegiadas sem armazenar segredos ou PII desnecessária."""

    __tablename__ = "auditoria_admin"
    __table_args__ = (
        Index("ix_auditoria_admin_entidade_id_criado", "entidade", "entidade_id", "criado_em"),
    )

    id = Column(Integer, primary_key=True)
    admin_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    acao = Column(String(80), nullable=False, index=True)
    entidade = Column(String(60), nullable=False, index=True)
    entidade_id = Column(String(80), nullable=True)
    detalhes = Column(JSON, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    admin = relationship("Usuario")
