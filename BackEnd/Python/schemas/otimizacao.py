from pydantic import BaseModel, Field


class LocalizacaoIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    raio_km: float = Field(default=15, ge=1, le=50)


class OtimizacaoConsultaIn(BaseModel):
    modo: str = Field(default="equilibrio", pattern="^(preco|distancia|avaliacao|equilibrio)$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EstabelecimentoProximoOut(BaseModel):
    fonte: str
    estabelecimento_id: int | None = None
    google_place_id: str | None = None
    nome: str
    tipo: str | None = None
    endereco: str | None = None
    latitude: float
    longitude: float
    distancia_km: float | None = None
    avaliacao: float | None = None
    quantidade_avaliacoes: int | None = None
    google_maps_uri: str | None = None
    parceiro_verificado: bool = False


class ItemOfertaOut(BaseModel):
    item_lista_id: int
    descricao: str
    produto_id: int
    produto_nome: str
    estabelecimento_id: int
    estabelecimento_nome: str
    quantidade_compra: float
    unidade_venda: str
    preco_unitario: float
    subtotal: float


class CestaEstabelecimentoOut(BaseModel):
    estabelecimento_id: int
    estabelecimento_nome: str
    total: float
    itens_encontrados: int
    itens_total: int
    cobertura_percentual: float
    distancia_km: float | None = None
    avaliacao: float | None = None
    quantidade_avaliacoes: int | None = None
    score_equilibrio: float | None = None
    itens: list[ItemOfertaOut]


class CompraOtimizadaOut(BaseModel):
    total: float | None
    economia_vs_melhor_loja: float | None
    estabelecimentos_usados: int
    itens: list[ItemOfertaOut]


class OtimizacaoOut(BaseModel):
    churrasco_id: int
    modo: str
    cestas: list[CestaEstabelecimentoOut]
    compra_otimizada: CompraOtimizadaOut
    aviso: str | None = None


class InteracaoEstabelecimentosIn(BaseModel):
    tipo: str
    estabelecimento_ids: list[int]
    churrasco_id: int | None = None
    contexto: str = "onde_comprar"
