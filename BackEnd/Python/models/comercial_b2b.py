"""Catálogo em massa e campanhas com aprovação, sem movimentação financeira."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from database.connection import Base


class ImportacaoCatalogo(Base):
    __tablename__ = "importacoes_catalogo"
    __table_args__ = (UniqueConstraint("organizacao_id", "chave_idempotencia", name="uq_importacoes_catalogo_org_chave"),)

    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    chave_idempotencia = Column(String(80), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    resultado = Column(JSON, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class CampanhaComercial(Base):
    __tablename__ = "campanhas_comerciais"
    __table_args__ = (
        UniqueConstraint("organizacao_id", "codigo", name="uq_campanha_org_codigo"),
    )

    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(60), nullable=False)
    nome = Column(String(150), nullable=False)
    descricao = Column(String(500), nullable=True)
    inicio_em = Column(DateTime, nullable=False)
    fim_em = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="rascunho", server_default="rascunho")
    criado_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    revisado_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    revisado_em = Column(DateTime, nullable=True)
    motivo_revisao = Column(String(400), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    itens = relationship("CampanhaComercialItem", back_populates="campanha", cascade="all, delete-orphan")


class CampanhaComercialItem(Base):
    __tablename__ = "campanhas_comerciais_itens"
    __table_args__ = (UniqueConstraint("campanha_id", "preco_id", name="uq_campanha_preco"),)

    id = Column(Integer, primary_key=True)
    campanha_id = Column(Integer, ForeignKey("campanhas_comerciais.id", ondelete="CASCADE"), nullable=False, index=True)
    preco_id = Column(Integer, ForeignKey("precos.id", ondelete="RESTRICT"), nullable=False, index=True)
    campanha = relationship("CampanhaComercial", back_populates="itens")
    preco = relationship("Preco")
