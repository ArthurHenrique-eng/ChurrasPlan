from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Estabelecimento(Base):
    __tablename__ = "estabelecimentos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_responsavel_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    slug = Column(String(170), nullable=False, unique=True, index=True)
    nome = Column(String(150), nullable=False)
    tipo = Column(String(60), nullable=False)
    endereco = Column(String(255), nullable=True)
    logradouro = Column(String(160), nullable=True)
    numero = Column(String(30), nullable=True)
    bairro = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=True, index=True)
    estado = Column(String(2), nullable=True, index=True)
    cep = Column(String(12), nullable=True)
    latitude = Column(Float, nullable=True, index=True)
    longitude = Column(Float, nullable=True, index=True)
    telefone = Column(String(30), nullable=True)
    site = Column(String(255), nullable=True)
    horario_funcionamento = Column(String(120), nullable=True)
    google_place_id = Column(String(255), nullable=True, unique=True, index=True)
    avaliacao = Column(Numeric(3, 2), nullable=True)
    quantidade_avaliacoes = Column(Integer, nullable=True)
    parceiro_verificado = Column(Boolean, nullable=False, default=False, server_default="0")
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")

    usuario_responsavel = relationship("Usuario", back_populates="estabelecimentos")
    precos = relationship("Preco", back_populates="estabelecimento", cascade="all, delete-orphan")
