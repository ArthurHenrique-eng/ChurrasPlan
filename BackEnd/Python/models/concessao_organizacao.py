"""Concessão administrativa B2B; NÃO representa pagamento ou assinatura adquirida."""
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class ConcessaoOrganizacao(Base):
    __tablename__ = "concessoes_organizacao"

    organizacao_id = Column(
        ForeignKey("organizacoes.id", ondelete="CASCADE"), primary_key=True
    )
    plano_slug = Column(String(20), nullable=False)
    origem = Column(String(30), nullable=False, default="cortesia_admin", server_default="cortesia_admin")
    expira_em = Column(DateTime, nullable=False)
    alterado_por_usuario_id = Column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    organizacao = relationship("Organizacao", back_populates="concessao")
