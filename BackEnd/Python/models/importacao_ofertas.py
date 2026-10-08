"""Importações idempotentes de ofertas comerciais por organização."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from database.connection import Base


class ImportacaoOfertas(Base):
    __tablename__ = "importacoes_ofertas"
    __table_args__ = (UniqueConstraint("organizacao_id", "chave_idempotencia", name="uq_importacao_ofertas_org_chave"),)

    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    chave_idempotencia = Column(String(80), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    resultado = Column(JSON, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    organizacao = relationship("Organizacao")
