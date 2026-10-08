"""Organizações B2B e membros. Papéis são locais à organização, não globais."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from database.connection import Base


class Organizacao(Base):
    __tablename__ = "organizacoes"

    id = Column(Integer, primary_key=True)
    slug = Column(String(150), nullable=False, unique=True, index=True)
    nome = Column(String(150), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    membros = relationship("OrganizacaoMembro", back_populates="organizacao")
    estabelecimentos = relationship("Estabelecimento", back_populates="organizacao")


class OrganizacaoMembro(Base):
    __tablename__ = "organizacao_membros"
    __table_args__ = (
        UniqueConstraint("organizacao_id", "usuario_id", name="uq_organizacao_membro"),
    )

    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    papel = Column(String(20), nullable=False, default="leitor", server_default="leitor")
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    organizacao = relationship("Organizacao", back_populates="membros")
    usuario = relationship("Usuario")
