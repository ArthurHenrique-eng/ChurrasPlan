"""Assinatura Premium pessoal isolada das assinaturas por organização."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from database.connection import Base


class AssinaturaStripeUsuario(Base):
    __tablename__ = "assinaturas_stripe_usuario"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id = Column(String(100), nullable=True, unique=True)
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    plano_slug = Column(String(30), nullable=False, server_default="free")
    periodicidade = Column(String(10), nullable=False, server_default="mensal")
    status = Column(String(30), nullable=False, server_default="sem_assinatura")
    periodo_fim_em = Column(DateTime, nullable=True)
    cancelamento_agendado = Column(Boolean, nullable=False, server_default="0")
    sincronizado_em = Column(DateTime, nullable=True)
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TentativaCheckoutUsuario(Base):
    __tablename__ = "tentativas_checkout_usuario"
    __table_args__ = (UniqueConstraint("usuario_id", "chave_idempotencia", name="uq_checkout_usuario_chave"),)
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    chave_idempotencia = Column(String(80), nullable=False)
    plano_slug = Column(String(30), nullable=False)
    periodicidade = Column(String(10), nullable=False)
    stripe_session_id = Column(String(130), nullable=False, unique=True)
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
