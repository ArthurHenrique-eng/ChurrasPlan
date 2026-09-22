from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class PlanoAssinatura(Base):
    __tablename__ = "planos_assinatura"

    id = Column(Integer, primary_key=True)
    slug = Column(String(50), nullable=False, unique=True, index=True)
    nome = Column(String(100), nullable=False)
    publico_alvo = Column(String(20), nullable=False, default="usuario")  # usuario | parceiro
    preco_mensal = Column(Numeric(12, 2), nullable=False, default=0)
    recursos = Column(JSON, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    assinaturas = relationship("AssinaturaUsuario", back_populates="plano")


class AssinaturaUsuario(Base):
    __tablename__ = "assinaturas_usuario"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    plano_id = Column(Integer, ForeignKey("planos_assinatura.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), nullable=False, default="ativa", server_default="ativa")
    provedor = Column(String(40), nullable=True)
    id_externo = Column(String(120), nullable=True, unique=True)
    iniciado_em = Column(DateTime, server_default=func.now(), nullable=False)
    termina_em = Column(DateTime, nullable=True)

    plano = relationship("PlanoAssinatura", back_populates="assinaturas")
