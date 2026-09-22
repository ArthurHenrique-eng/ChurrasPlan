from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from config import LIMITES, FATORES_TIPO_EVENTO
from utils.validators import validar_perfil_personalizado

PerfilConsumo = Literal["leve", "normal", "alto", "personalizado"]
TipoEvento = Literal["almoco", "jantar", "aniversario", "confraternizacao_empresa", "evento_prolongado", "outro"]


class PerfilPersonalizado(BaseModel):
    carne_adulto_kg: Optional[float] = Field(default=None, ge=0)
    carne_crianca_kg: Optional[float] = Field(default=None, ge=0)
    agua_litros_pessoa: Optional[float] = Field(default=None, ge=0)
    refrigerante_litros_pessoa: Optional[float] = Field(default=None, ge=0)
    suco_litros_pessoa: Optional[float] = Field(default=None, ge=0)
    cerveja_litros_consumidor_hora: Optional[float] = Field(default=None, ge=0)
    gelo_kg_pessoa: Optional[float] = Field(default=None, ge=0)
    carvao_kg_por_kg_carne: Optional[float] = Field(default=None, ge=0)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class CarneSelecionada(BaseModel):
    nome: str
    produto_slug: Optional[str] = None
    percentual: float = Field(ge=LIMITES["percentual_min"], le=LIMITES["percentual_max"])


class CompraCalculada(BaseModel):
    necessario: float
    unidade_necessaria: str
    compra: float
    unidade_compra: str
    quantidade_embalagens: Optional[int] = None
    unidade_venda: str
    tamanho_embalagem: Optional[float] = None
    unidade_embalagem: Optional[str] = None


class CalculoCarnesRequest(BaseModel):
    homens: int = Field(ge=0, le=LIMITES["pessoas_max"])
    mulheres: int = Field(ge=0, le=LIMITES["pessoas_max"])
    criancas: int = Field(ge=0, le=LIMITES["pessoas_max"])
    duracao_horas: float = Field(ge=LIMITES["duracao_horas_min"], le=LIMITES["duracao_horas_max"])
    tipo_evento: TipoEvento = "outro"
    perfil_consumo: PerfilConsumo
    perfil_personalizado: Optional[PerfilPersonalizado] = None
    carnes: list[CarneSelecionada]
    carvao_ativo: bool = True
    total_kg_manual: Optional[float] = Field(default=None, ge=0)

    @field_validator("carnes")
    @classmethod
    def validar_soma_percentual(cls, carnes):
        soma = sum(c.percentual for c in carnes)
        if carnes and abs(soma - 100) > LIMITES["tolerancia_soma_percentual"]:
            raise ValueError(f"A soma dos percentuais deve ser 100%. Valor atual: {soma:.2f}%")
        return carnes

    @model_validator(mode="after")
    def validar_cruzado(self):
        total = self.homens + self.mulheres + self.criancas
        if total <= 0:
            raise ValueError("Informe pelo menos um convidado.")
        if total > LIMITES["pessoas_max"]:
            raise ValueError(f"O total de convidados não pode ultrapassar {LIMITES['pessoas_max']}.")
        perfil_dict = self.perfil_personalizado.to_dict() if self.perfil_personalizado else None
        validar_perfil_personalizado(self.perfil_consumo, perfil_dict)
        return self


class ItemCarneResponse(BaseModel):
    nome: str
    produto_slug: str
    percentual: float
    quantidade_kg: float
    quantidade_compra_kg: float
    quantidade_embalagens: Optional[int] = None
    unidade_venda: str


class CalculoCarnesResponse(BaseModel):
    total_kg: float
    itens: list[ItemCarneResponse]
    carvao_necessario_kg: float
    carvao_compra_kg: float
    carvao_sacos: int


class CalculoBebidasRequest(BaseModel):
    homens: int = Field(ge=0, le=LIMITES["pessoas_max"])
    mulheres: int = Field(ge=0, le=LIMITES["pessoas_max"])
    criancas: int = Field(ge=0, le=LIMITES["pessoas_max"])
    homens_bebem_alcool: int = Field(ge=0)
    mulheres_bebem_alcool: int = Field(ge=0)
    duracao_horas: float = Field(ge=LIMITES["duracao_horas_min"], le=LIMITES["duracao_horas_max"])
    tipo_evento: TipoEvento = "outro"
    perfil_consumo: PerfilConsumo
    perfil_personalizado: Optional[PerfilPersonalizado] = None
    bebidas_nao_alcoolicas_ativas: list[str] = Field(default_factory=list)
    bebida_alcoolica_ativa: bool = False
    gelo_ativo: bool = False

    @model_validator(mode="after")
    def validar_cruzado(self):
        total = self.homens + self.mulheres + self.criancas
        if total <= 0:
            raise ValueError("Informe pelo menos um convidado.")
        if total > LIMITES["pessoas_max"]:
            raise ValueError(f"O total de convidados não pode ultrapassar {LIMITES['pessoas_max']}.")
        if self.homens_bebem_alcool > self.homens:
            raise ValueError("homens_bebem_alcool não pode ser maior que homens")
        if self.mulheres_bebem_alcool > self.mulheres:
            raise ValueError("mulheres_bebem_alcool não pode ser maior que mulheres")
        perfil_dict = self.perfil_personalizado.to_dict() if self.perfil_personalizado else None
        validar_perfil_personalizado(self.perfil_consumo, perfil_dict)
        return self


class CalculoBebidasResponse(BaseModel):
    nao_alcoolicas_litros: dict[str, float]
    nao_alcoolicas_compra: dict[str, CompraCalculada]
    alcool_litros_total: float
    alcool_unidades_sugeridas: int
    alcool_unidade_venda: str
    gelo_kg: float
    gelo_compra_kg: float
    gelo_sacos: int


class CalculoExtrasRequest(BaseModel):
    pessoas_total: int = Field(gt=0, le=LIMITES["pessoas_max"])
    carne_total_kg: float = Field(ge=0)
    extras_ativos: list[str] = Field(default_factory=list)
    acompanhamentos_ativos: list[str] = Field(default_factory=list)


class CalculoExtrasResponse(BaseModel):
    extras: dict[str, float]
    acompanhamentos: dict[str, float]
