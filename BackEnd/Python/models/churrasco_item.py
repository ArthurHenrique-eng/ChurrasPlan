from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import declared_attr, relationship

from database.connection import Base


class ItemCalculadoMixin:
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True, index=True)
    preco_id = Column(Integer, ForeignKey("precos.id", ondelete="SET NULL"), nullable=True)
    produto_slug = Column(String(140), nullable=True, index=True)
    nome_item = Column(String(120), nullable=False)

    quantidade_necessaria = Column(Numeric(12, 3), nullable=False)
    unidade_necessaria = Column(String(30), nullable=False)
    quantidade_compra = Column(Numeric(12, 3), nullable=False)
    unidade_compra = Column(String(30), nullable=False)
    quantidade_embalagens = Column(Integer, nullable=True)
    tamanho_embalagem = Column(Numeric(12, 3), nullable=True)
    unidade_embalagem = Column(String(30), nullable=True)
    unidade_venda = Column(String(30), nullable=False)

    # Snapshot financeiro: histórico continua consistente mesmo que o preço mude.
    preco_unitario = Column(Numeric(12, 2), nullable=True)
    subtotal_estimado = Column(Numeric(12, 2), nullable=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id", ondelete="SET NULL"), nullable=True)

    @declared_attr
    def produto(cls):
        return relationship("Produto")

    @declared_attr
    def preco(cls):
        return relationship("Preco")

    @declared_attr
    def estabelecimento(cls):
        return relationship("Estabelecimento")


class ChurrascoCarne(ItemCalculadoMixin, Base):
    __tablename__ = "churrasco_carnes"

    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, index=True)
    percentual = Column(Numeric(6, 2), nullable=False)
    churrasco = relationship("Churrasco", back_populates="carnes")


class ChurrascoBebida(ItemCalculadoMixin, Base):
    __tablename__ = "churrasco_bebidas"

    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, index=True)
    churrasco = relationship("Churrasco", back_populates="bebidas")


class ChurrascoExtra(ItemCalculadoMixin, Base):
    __tablename__ = "churrasco_extras"

    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)
    churrasco = relationship("Churrasco", back_populates="itens_extra")
