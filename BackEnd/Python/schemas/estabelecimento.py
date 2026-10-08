from datetime import datetime
from math import isfinite
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EstabelecimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_responsavel_id: Optional[int] = None
    organizacao_id: Optional[int] = None
    slug: str
    nome: str
    tipo: str
    endereco: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    telefone: Optional[str] = None
    site: Optional[str] = None
    horario_funcionamento: Optional[str] = None
    avaliacao: Optional[float] = None
    quantidade_avaliacoes: Optional[int] = None
    parceiro_verificado: bool = False
    ativo: bool
    distancia_km: Optional[float] = None


def _normalizar_coordenada(valor, limite: float):
    """Aceita graus decimais; nunca infere micrograus de inteiros ambíguos."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        raise ValueError("Coordenada inválida. Informe graus decimais.")
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        if ("," in texto and "." in texto) or texto.count(",") > 1:
            raise ValueError("Formato de coordenada inválido. Use graus decimais, como -19,959383.")
        valor = texto.replace(",", ".")

    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError) as erro:
        raise ValueError("Coordenada inválida. Informe graus decimais.") from erro
    if not isfinite(numero):
        raise ValueError("Coordenada inválida. Informe um número finito em graus decimais.")
    if abs(numero) > limite:
        raise ValueError(
            f"Coordenada fora do intervalo de -{limite:g} a {limite:g}. "
            "Informe graus decimais (ex.: -19,959383)."
        )
    return numero


class EstabelecimentoParceiroCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    tipo: str = Field(default="mercado", max_length=60)
    endereco: Optional[str] = Field(default=None, max_length=255)
    logradouro: Optional[str] = Field(default=None, max_length=160)
    numero: Optional[str] = Field(default=None, max_length=30)
    bairro: Optional[str] = Field(default=None, max_length=100)
    cidade: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, min_length=2, max_length=2)
    cep: Optional[str] = Field(default=None, max_length=12)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @field_validator("latitude", mode="before")
    @classmethod
    def normalizar_latitude(cls, valor):
        return _normalizar_coordenada(valor, 90)

    @field_validator("longitude", mode="before")
    @classmethod
    def normalizar_longitude(cls, valor):
        return _normalizar_coordenada(valor, 180)
    telefone: Optional[str] = Field(default=None, max_length=30)
    site: Optional[str] = Field(default=None, max_length=255)
    horario_funcionamento: Optional[str] = Field(default=None, max_length=120)


class PrecoComparacaoItem(BaseModel):
    preco_id: int
    produto_id: int
    produto: str
    estabelecimento_id: int
    estabelecimento: str
    preco: float
    preco_original: Optional[float] = None
    unidade_venda: str
    coletado_em: str
    data_atualizacao: str
    inicio_validade: Optional[str] = None
    fim_validade: Optional[str] = None
    estoque_status: str = "disponivel"
    fonte: Optional[str] = None
    origem: str = "manual"


class PrecoParceiroCreate(BaseModel):
    produto_id: int
    estabelecimento_id: int
    preco: float = Field(gt=0, le=10_000_000)
    preco_original: Optional[float] = Field(default=None, gt=0, le=10_000_000)
    inicio_validade: Optional[datetime] = None
    fim_validade: Optional[datetime] = None
    estoque_status: str = Field(default="disponivel", max_length=30)


class ResumoPrecoOut(BaseModel):
    produto_id: int
    produto_nome: str
    preco_mais_recente_historico: Optional[float] = None
    preco_medio_historico: Optional[float] = None
    preco_minimo_atual: Optional[float] = None
    preco_maximo_atual: Optional[float] = None
    quantidade_estabelecimentos: int
    melhor_estabelecimento_id: Optional[int] = None
    melhor_estabelecimento_nome: Optional[str] = None
