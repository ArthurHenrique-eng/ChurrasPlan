"""Fonte de verdade das assinaturas por organização. Nunca usar assinaturas_usuario para B2B."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from database.connection import Base


class AssinaturaOrganizacao(Base):
    __tablename__ = "assinaturas_organizacao"
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id = Column(String(100), nullable=True, unique=True)
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    plano_slug = Column(String(20), nullable=False, server_default="free")
    status = Column(String(30), nullable=False, server_default="sem_assinatura")
    periodo_fim_em = Column(DateTime, nullable=True)
    tolerancia_ate = Column(DateTime, nullable=True)
    cancelamento_agendado = Column(Boolean, nullable=False, server_default="0")
    sincronizado_em = Column(DateTime, nullable=True)
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TentativaCheckout(Base):
    __tablename__ = "tentativas_checkout"
    __table_args__ = (UniqueConstraint("organizacao_id", "chave_idempotencia", name="uq_checkout_org_chave"),)
    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    chave_idempotencia = Column(String(80), nullable=False)
    plano_slug = Column(String(20), nullable=False)
    stripe_session_id = Column(String(130), nullable=False, unique=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class EventoBilling(Base):
    __tablename__ = "eventos_billing"
    event_id = Column(String(130), primary_key=True)
    event_type = Column(String(100), nullable=False)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="SET NULL"), nullable=True)
    resultado = Column(String(40), nullable=False)
    registrado_em = Column(DateTime, nullable=False, server_default=func.now())
