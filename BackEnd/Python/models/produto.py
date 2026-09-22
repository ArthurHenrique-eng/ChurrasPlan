from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from database.connection import Base


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False, index=True)
    produto_pai_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True, index=True)
    tipo_produto = Column(String(20), nullable=False, default="generico", server_default="generico", index=True)  # generico | comercial
    slug = Column(String(140), nullable=False, unique=True, index=True)
    nome = Column(String(120), nullable=False)
    marca = Column(String(100), nullable=True, index=True)
    variante = Column(String(120), nullable=True)
    fabricante = Column(String(120), nullable=True)
    ean = Column(String(32), nullable=True, unique=True, index=True)
    sku = Column(String(80), nullable=True, index=True)

    unidade_consumo = Column(String(30), nullable=False)
    unidade_venda = Column(String(30), nullable=False)
    venda_fracionada = Column(Boolean, nullable=False, default=False)
    incremento_venda = Column(Numeric(12, 3), nullable=True)
    quantidade_embalagem = Column(Numeric(12, 3), nullable=True)
    unidade_embalagem = Column(String(30), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")

    imagem_url = Column(String(255), nullable=True)
    descricao = Column(Text, nullable=True)

    categoria = relationship("Categoria")
    produto_pai = relationship("Produto", remote_side=[id], back_populates="variantes")
    variantes = relationship("Produto", back_populates="produto_pai")
    precos = relationship("Preco", back_populates="produto", cascade="all, delete-orphan")
