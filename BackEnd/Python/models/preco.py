from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class Preco(Base):
    __tablename__ = "precos"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    criado_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    preco = Column(Numeric(12, 2), nullable=False)
    preco_original = Column(Numeric(12, 2), nullable=True)
    moeda = Column(String(3), nullable=False, default="BRL", server_default="BRL")
    fonte = Column(String(255), nullable=True)
    origem = Column(String(40), nullable=False, default="manual", server_default="manual")
    estoque_status = Column(String(30), nullable=False, default="disponivel", server_default="disponivel")
    disponivel = Column(Boolean, nullable=False, default=True, server_default="1")
    inicio_validade = Column(DateTime, nullable=True)
    fim_validade = Column(DateTime, nullable=True)
    coletado_em = Column(DateTime, server_default=func.now(), nullable=False)
    data_atualizacao = Column(DateTime, server_default=func.now(), nullable=False)

    produto = relationship("Produto", back_populates="precos")
    estabelecimento = relationship("Estabelecimento", back_populates="precos")
