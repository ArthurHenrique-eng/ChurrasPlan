from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EstabelecimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_responsavel_id: Optional[int] = None
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
    google_place_id: Optional[str] = None
    avaliacao: Optional[float] = None
    quantidade_avaliacoes: Optional[int] = None
    parceiro_verificado: bool = False
    ativo: bool
    distancia_km: Optional[float] = None


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
