from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from config import LIMITES
from schemas.calculadora import CarneSelecionada, PerfilConsumo, PerfilPersonalizado, TipoEvento
from utils.validators import validar_perfil_personalizado


class ChurrascoCreate(BaseModel):
    nome: Optional[str] = Field(default=None, max_length=150)
    chave_cliente: Optional[str] = Field(default=None, min_length=8, max_length=64)
    data_evento: Optional[datetime] = None
    tipo_evento: TipoEvento
    duracao_horas: float = Field(ge=LIMITES["duracao_horas_min"], le=LIMITES["duracao_horas_max"])
    perfil_consumo: PerfilConsumo
    perfil_personalizado: Optional[PerfilPersonalizado] = None

    # API nova: adultos. Campos legados por sexo continuam aceitos para não
    # quebrar clientes/testes antigos.
    adultos: Optional[int] = Field(default=None, ge=0, le=LIMITES["pessoas_max"])
    adultos_bebem_alcool: Optional[int] = Field(default=None, ge=0)
    homens: int = Field(default=0, ge=0, le=LIMITES["pessoas_max"])
    mulheres: int = Field(default=0, ge=0, le=LIMITES["pessoas_max"])
    criancas: int = Field(default=0, ge=0, le=LIMITES["pessoas_max"])
    homens_bebem_alcool: int = Field(default=0, ge=0)
    mulheres_bebem_alcool: int = Field(default=0, ge=0)

    vegetarianos: int = Field(default=0, ge=0)
    veganos: int = Field(default=0, ge=0)
    sem_carne_bovina: int = Field(default=0, ge=0)
    sem_carne_suina: int = Field(default=0, ge=0)
    intolerantes_lactose: int = Field(default=0, ge=0)
    alergias: Optional[str] = Field(default=None, max_length=2000)
    outras_restricoes: Optional[str] = Field(default=None, max_length=2000)

    orcamento_maximo: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    dividir_entre: Optional[int] = Field(default=None, ge=2, le=LIMITES["pessoas_max"])

    carnes: list[CarneSelecionada]
    carvao_ativo: bool = True
    bebidas_nao_alcoolicas_ativas: list[str] = Field(default_factory=list)
    bebida_alcoolica_ativa: bool = False
    gelo_ativo: bool = False
    extras_ativos: list[str] = Field(default_factory=list)
    acompanhamentos_ativos: list[str] = Field(default_factory=list)

    @property
    def total_adultos(self) -> int:
        return self.adultos if self.adultos is not None else self.homens + self.mulheres

    @property
    def total_adultos_bebem(self) -> int:
        return self.adultos_bebem_alcool if self.adultos_bebem_alcool is not None else self.homens_bebem_alcool + self.mulheres_bebem_alcool

    @property
    def total_pessoas(self) -> int:
        return self.total_adultos + self.criancas

    @model_validator(mode="after")
    def validar_regras_cruzadas(self):
        if self.adultos is None:
            if self.homens_bebem_alcool > self.homens:
                raise ValueError("homens_bebem_alcool não pode ser maior que homens")
            if self.mulheres_bebem_alcool > self.mulheres:
                raise ValueError("mulheres_bebem_alcool não pode ser maior que mulheres")
        if self.total_adultos_bebem > self.total_adultos:
            raise ValueError("adultos_bebem_alcool não pode ser maior que o total de adultos")
        total = self.total_pessoas
        if total <= 0:
            raise ValueError("Informe pelo menos um convidado.")
        if total > LIMITES["pessoas_max"]:
            raise ValueError(f"O total de convidados não pode ultrapassar {LIMITES['pessoas_max']}.")
        for campo in ["vegetarianos", "veganos", "sem_carne_bovina", "sem_carne_suina", "intolerantes_lactose"]:
            if getattr(self, campo) > total:
                raise ValueError(f"{campo} não pode ser maior que o total de convidados.")
        if self.vegetarianos + self.veganos > total:
            raise ValueError("A soma de vegetarianos e veganos não pode ultrapassar o total de convidados.")
        perfil_dict = self.perfil_personalizado.to_dict() if self.perfil_personalizado else None
        validar_perfil_personalizado(self.perfil_consumo, perfil_dict)
        return self


class ItemResultado(BaseModel):
    produto_id: Optional[int] = None
    produto_slug: Optional[str] = None
    percentual: Optional[float] = None
    nome: str
    categoria: str
    quantidade_necessaria: float
    unidade_necessaria: str
    quantidade_compra: float
    unidade_compra: str
    quantidade_embalagens: Optional[int] = None
    tamanho_embalagem: Optional[float] = None
    unidade_embalagem: Optional[str] = None
    unidade_venda: str
    preco_estimado: Optional[float] = None
    preco_fonte: Optional[str] = None
    estabelecimento_id: Optional[int] = None
    estabelecimento_nome: Optional[str] = None
    subtotal_estimado: Optional[float] = None


class ChurrascoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: Optional[int] = None
    nome: Optional[str]
    status: str = "rascunho"
    data_evento: Optional[datetime] = None
    tipo_evento: str
    duracao_horas: float
    perfil_consumo: str
    perfil_personalizado: Optional[dict] = None
    adultos: int
    adultos_bebem_alcool: int
    # Compatibilidade de saída para clientes antigos.
    homens: int = 0
    mulheres: int = 0
    criancas: int
    total_pessoas: int
    vegetarianos: int = 0
    veganos: int = 0
    sem_carne_bovina: int = 0
    sem_carne_suina: int = 0
    intolerantes_lactose: int = 0
    alergias: Optional[str] = None
    outras_restricoes: Optional[str] = None
    orcamento_maximo: Optional[float] = None
    orcamento_status: Optional[str] = None
    orcamento_diferenca: Optional[float] = None
    dividir_entre: Optional[int] = None
    valor_por_divisao: Optional[float] = None
    base_divisao: Optional[str] = None
    carne_total_kg: float
    carvao_ativo: bool
    gelo_ativo: bool
    carvao_necessario_kg: Optional[float] = None
    carvao_compra_kg: float
    itens: list[ItemResultado]
    custo_total_estimado: Optional[float]
    custo_por_pessoa: Optional[float]
    estimativa_precos_completa: bool = False
    itens_com_preco: int = 0
    itens_sem_preco: int = 0
    custo_total_real: Optional[float] = None
    custo_real_completo: bool = False
    aviso_precos: Optional[str] = None
    avisos_restricoes: list[str] = Field(default_factory=list)


class ChurrascoHistoricoOut(BaseModel):
    id: int
    nome: Optional[str]
    data_evento: Optional[datetime]
    tipo_evento: str
    total_pessoas: int
    custo_total_estimado: Optional[float]
    estimativa_precos_completa: bool = False
    status: str
    criado_em: datetime
    atualizado_em: datetime


class RepetirChurrascoIn(BaseModel):
    nome: Optional[str] = Field(default=None, max_length=150)
    data_evento: Optional[datetime] = None
    adultos: Optional[int] = Field(default=None, ge=0, le=LIMITES["pessoas_max"])
    criancas: Optional[int] = Field(default=None, ge=0, le=LIMITES["pessoas_max"])
    adultos_bebem_alcool: Optional[int] = Field(default=None, ge=0, le=LIMITES["pessoas_max"])


class ClaimChurrascoIn(BaseModel):
    chave_cliente: str = Field(min_length=8, max_length=64)


class DivisaoChurrascoIn(BaseModel):
    dividir_entre: Optional[int] = Field(default=None, ge=2, le=LIMITES["pessoas_max"])
