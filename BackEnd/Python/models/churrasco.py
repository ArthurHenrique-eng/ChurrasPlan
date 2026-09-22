from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from database.connection import Base


class Churrasco(Base):
    __tablename__ = "churrascos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    nome = Column(String(150), nullable=True)
    chave_cliente = Column(String(64), nullable=True, unique=True, index=True)
    status = Column(String(20), nullable=False, default="rascunho", server_default="rascunho", index=True)
    data_evento = Column(DateTime, nullable=True, index=True)
    tipo_evento = Column(String(60), nullable=False)
    duracao_horas = Column(Float, nullable=False)
    perfil_consumo = Column(String(20), nullable=False)
    perfil_personalizado = Column(JSON, nullable=True)

    # Campos novos. Os campos por sexo são mantidos para compatibilidade com
    # históricos e clientes antigos, mas o fluxo novo trabalha com adultos.
    adultos = Column(Integer, nullable=True)
    adultos_bebem_alcool = Column(Integer, nullable=True)
    homens = Column(Integer, nullable=False, default=0)
    mulheres = Column(Integer, nullable=False, default=0)
    criancas = Column(Integer, nullable=False, default=0)
    homens_bebem_alcool = Column(Integer, nullable=False, default=0)
    mulheres_bebem_alcool = Column(Integer, nullable=False, default=0)

    vegetarianos = Column(Integer, nullable=False, default=0, server_default="0")
    veganos = Column(Integer, nullable=False, default=0, server_default="0")
    sem_carne_bovina = Column(Integer, nullable=False, default=0, server_default="0")
    sem_carne_suina = Column(Integer, nullable=False, default=0, server_default="0")
    intolerantes_lactose = Column(Integer, nullable=False, default=0, server_default="0")
    alergias = Column(Text, nullable=True)
    outras_restricoes = Column(Text, nullable=True)

    orcamento_maximo = Column(Numeric(12, 2), nullable=True)
    dividir_entre = Column(Integer, nullable=True)

    carne_total_kg = Column(Numeric(12, 3), nullable=True)
    carvao_ativo = Column(Boolean, nullable=False, default=True)
    gelo_ativo = Column(Boolean, nullable=False, default=False)
    carvao_necessario_kg = Column(Numeric(12, 3), nullable=True)
    carvao_compra_kg = Column(Numeric(12, 3), nullable=True)

    custo_total_estimado = Column(Numeric(12, 2), nullable=True)
    custo_por_pessoa = Column(Numeric(12, 2), nullable=True)

    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="churrascos")
    carnes = relationship("ChurrascoCarne", back_populates="churrasco", cascade="all, delete-orphan", passive_deletes=True)
    bebidas = relationship("ChurrascoBebida", back_populates="churrasco", cascade="all, delete-orphan", passive_deletes=True)
    itens_extra = relationship("ChurrascoExtra", back_populates="churrasco", cascade="all, delete-orphan", passive_deletes=True)
    lista_compras = relationship("ListaCompras", back_populates="churrasco", uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    convite = relationship("ConviteChurrasco", back_populates="churrasco", uselist=False, cascade="all, delete-orphan", passive_deletes=True)

    @property
    def total_adultos(self) -> int:
        return int(self.adultos if self.adultos is not None else (self.homens + self.mulheres))

    @property
    def total_adultos_bebem(self) -> int:
        return int(self.adultos_bebem_alcool if self.adultos_bebem_alcool is not None else (self.homens_bebem_alcool + self.mulheres_bebem_alcool))

    @property
    def total_pessoas(self) -> int:
        return self.total_adultos + self.criancas
