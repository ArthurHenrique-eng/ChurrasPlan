from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from database.connection import Base


class ConsentimentoUsuario(Base):
    """Registro mínimo de aceite de documentos legais versionados.

    Não guarda IP ou localização. O objetivo é comprovar qual versão do
    documento estava vigente quando o usuário concedeu/retirou o aceite.
    """

    __tablename__ = "consentimentos_usuario"
    __table_args__ = (
        UniqueConstraint("usuario_id", "tipo", "versao", name="uq_consentimento_usuario_tipo_versao"),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False, index=True)  # termos | privacidade | marketing
    versao = Column(String(30), nullable=False)
    concedido = Column(Boolean, nullable=False, default=True, server_default="1")
    origem = Column(String(40), nullable=False, default="cadastro", server_default="cadastro")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    usuario = relationship("Usuario", back_populates="consentimentos")
