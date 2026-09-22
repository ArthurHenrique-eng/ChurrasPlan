from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from database.connection import Base


class ConviteChurrasco(Base):
    __tablename__ = "convites_churrasco"

    id = Column(Integer, primary_key=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    codigo = Column(String(32), nullable=False, unique=True, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    expira_em = Column(DateTime, nullable=True)

    churrasco = relationship("Churrasco", back_populates="convite")
    respostas = relationship("RespostaConvite", back_populates="convite", cascade="all, delete-orphan", passive_deletes=True)


class RespostaConvite(Base):
    __tablename__ = "respostas_convite"

    id = Column(Integer, primary_key=True)
    convite_id = Column(Integer, ForeignKey("convites_churrasco.id", ondelete="CASCADE"), nullable=False, index=True)
    chave_resposta = Column(String(48), nullable=False, unique=True, index=True)
    nome = Column(String(120), nullable=False)
    resposta = Column(String(20), nullable=False, index=True)  # confirmado | talvez | nao
    tipo_convidado = Column(String(20), nullable=False, default="adulto")  # adulto | crianca
    consome_alcool = Column(Boolean, nullable=False, default=False)
    vegetariano = Column(Boolean, nullable=False, default=False)
    vegano = Column(Boolean, nullable=False, default=False)
    sem_carne_bovina = Column(Boolean, nullable=False, default=False)
    sem_carne_suina = Column(Boolean, nullable=False, default=False)
    intolerante_lactose = Column(Boolean, nullable=False, default=False)
    alergias = Column(Text, nullable=True)
    outras_restricoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    convite = relationship("ConviteChurrasco", back_populates="respostas")
