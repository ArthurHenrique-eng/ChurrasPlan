from sqlalchemy import Column, ForeignKey, Integer, String
from database.connection import Base


class ConsumoAssistente(Base):
    __tablename__ = "consumo_assistente"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    dia = Column(String(10), primary_key=True)
    quantidade = Column(Integer, nullable=False, default=0, server_default="0")
