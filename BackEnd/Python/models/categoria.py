from sqlalchemy import Column, Integer, String

from database.connection import Base


class Categoria(Base):
    """
    Categoria de produto: carne, bebida, extra ou acompanhamento.
    Mantida em tabela propria (em vez de um Enum fixo) para permitir criar
    novas categorias no futuro sem alterar o schema.
    """
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(60), nullable=False, unique=True)
    tipo = Column(String(30), nullable=False)  # carne | bebida | extra | acompanhamento
