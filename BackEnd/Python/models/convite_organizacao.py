"""Convites B2B: token opaco não persistido em texto puro, consumo único."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, Index, JSON
from sqlalchemy.orm import relationship
from database.connection import Base


class ConviteOrganizacao(Base):
    __tablename__ = "convites_organizacao"
    __table_args__ = (Index("ix_convite_org_org_email", "organizacao_id", "email"),)

    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(160), nullable=False)
    papel = Column(String(20), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    criado_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    expira_em = Column(DateTime, nullable=False)
    usado_em = Column(DateTime, nullable=True)
    revogado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    organizacao = relationship("Organizacao", back_populates="convites")


class AuditoriaOrganizacao(Base):
    __tablename__ = "auditoria_organizacao"
    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    autor_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    acao = Column(String(60), nullable=False)
    alvo_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    detalhes = Column(JSON, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
