"""Snapshots reutilizáveis de eventos Premium, sempre vinculados ao titular."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, func
from database.connection import Base


class ModeloEventoUsuario(Base):
    __tablename__ = "modelos_evento_usuario"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    dados = Column(JSON, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
