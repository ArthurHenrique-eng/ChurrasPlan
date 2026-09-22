from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    papel = Column(String(20), nullable=False, default="usuario", server_default="usuario", index=True)  # usuario | parceiro | admin
    plano = Column(String(30), nullable=False, default="gratuito", server_default="gratuito")
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")
    email_verificado_em = Column(DateTime, nullable=True)
    ultimo_login_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    churrascos = relationship("Churrasco", back_populates="usuario")
    sessoes = relationship("SessaoUsuario", back_populates="usuario", cascade="all, delete-orphan")
    tokens = relationship("TokenUsuario", back_populates="usuario", cascade="all, delete-orphan")
    estabelecimentos = relationship("Estabelecimento", back_populates="usuario_responsavel")
    consentimentos = relationship("ConsentimentoUsuario", back_populates="usuario", cascade="all, delete-orphan")
