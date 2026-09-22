from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class SessaoUsuario(Base):
    __tablename__ = "sessoes_usuario"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    csrf_hash = Column(String(64), nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    ultimo_uso_em = Column(DateTime, server_default=func.now(), nullable=False)
    expira_em = Column(DateTime, nullable=False, index=True)
    revogada = Column(Boolean, nullable=False, default=False)
    user_agent = Column(String(255), nullable=True)
    ip_hash = Column(String(64), nullable=True)

    usuario = relationship("Usuario", back_populates="sessoes")


class TokenUsuario(Base):
    __tablename__ = "tokens_usuario"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False, index=True)  # verificar_email | redefinir_senha
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    expira_em = Column(DateTime, nullable=False)
    usado_em = Column(DateTime, nullable=True)

    usuario = relationship("Usuario", back_populates="tokens")
