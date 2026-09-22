from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class ListaCompras(Base):
    __tablename__ = "lista_compras"

    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    churrasco = relationship("Churrasco", back_populates="lista_compras")
    itens = relationship("ListaComprasItem", back_populates="lista", cascade="all, delete-orphan", passive_deletes=True)

    @property
    def valor_pago_total(self):
        return sum(float(i.valor_pago_total or 0) for i in self.itens if i.comprado)


class ListaComprasItem(Base):
    __tablename__ = "lista_compras_itens"

    id = Column(Integer, primary_key=True, index=True)
    lista_compras_id = Column(Integer, ForeignKey("lista_compras.id", ondelete="CASCADE"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True)
    estabelecimento_compra_id = Column(Integer, ForeignKey("estabelecimentos.id", ondelete="SET NULL"), nullable=True)
    descricao = Column(String(150), nullable=False)
    quantidade = Column(Numeric(12, 3), nullable=False)
    unidade = Column(String(30), nullable=False)
    quantidade_embalagens = Column(Integer, nullable=True)
    unidade_venda = Column(String(30), nullable=False)
    categoria = Column(String(30), nullable=False)
    preco_unitario = Column(Numeric(12, 2), nullable=True)
    subtotal_estimado = Column(Numeric(12, 2), nullable=True)
    valor_pago_total = Column(Numeric(12, 2), nullable=True)
    comprado = Column(Boolean, nullable=False, default=False, server_default="0")
    comprado_em = Column(DateTime, nullable=True)

    lista = relationship("ListaCompras", back_populates="itens")
    produto = relationship("Produto")
    estabelecimento_compra = relationship("Estabelecimento")
