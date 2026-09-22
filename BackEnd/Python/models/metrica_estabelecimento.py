from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from database.connection import Base


class MetricaEstabelecimento(Base):
    """Evento mínimo de descoberta de um estabelecimento.

    Não armazena localização do usuário, IP, user_id, churrasco_id ou identificadores de
    sessão. O objetivo é somente oferecer ao parceiro métricas agregadas de
    visualizações e cliques dentro da experiência "Onde comprar".
    """

    __tablename__ = "metricas_estabelecimentos"
    __table_args__ = (
        CheckConstraint("tipo IN ('visualizacao','clique')", name="ck_metricas_estabelecimentos_tipo"),
        Index(
            "ix_metricas_estabelecimentos_estabelecimento_tipo_criado",
            "estabelecimento_id", "tipo", "criado_em",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    estabelecimento_id = Column(
        Integer, ForeignKey("estabelecimentos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tipo = Column(String(20), nullable=False, index=True)
    contexto = Column(String(40), nullable=False, default="onde_comprar", server_default="onde_comprar")
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    estabelecimento = relationship("Estabelecimento")
