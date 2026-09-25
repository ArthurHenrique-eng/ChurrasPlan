from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProdutoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    produto_pai_id: Optional[int] = None
    tipo_produto: str = "generico"
    slug: str
    nome: str
    categoria_id: int
    categoria_nome: Optional[str] = None
    categoria_tipo: Optional[str] = None
    marca: Optional[str] = None
    variante: Optional[str] = None
    fabricante: Optional[str] = None
    ean: Optional[str] = None
    sku: Optional[str] = None
    unidade_consumo: str
    unidade_venda: str
    venda_fracionada: bool
    incremento_venda: Optional[float] = None
    quantidade_embalagem: Optional[float] = None
    unidade_embalagem: Optional[str] = None
    ativo: bool
    imagem_url: Optional[str] = None
    descricao: Optional[str] = None
    preco_medio_historico: Optional[float] = None
    preco_minimo_atual: Optional[float] = None


class ProdutoComercialCreate(BaseModel):
    produto_pai_id: int
    nome: str = Field(min_length=2, max_length=120)
    marca: str = Field(min_length=1, max_length=100)
    variante: Optional[str] = Field(default=None, max_length=120)
    fabricante: Optional[str] = Field(default=None, max_length=120)
    ean: Optional[str] = Field(default=None, min_length=8, max_length=32)
    sku: Optional[str] = Field(default=None, max_length=80)
    unidade_venda: str = Field(min_length=1, max_length=30)
    quantidade_embalagem: float = Field(gt=0, le=1_000_000)
    unidade_embalagem: str = Field(min_length=1, max_length=30)
    imagem_url: Optional[str] = Field(default=None, max_length=255)
    descricao: Optional[str] = Field(default=None, max_length=4000)


class ProdutoComercialUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    marca: Optional[str] = Field(default=None, min_length=1, max_length=100)
    variante: Optional[str] = Field(default=None, max_length=120)
    fabricante: Optional[str] = Field(default=None, max_length=120)
    ean: Optional[str] = Field(default=None, min_length=8, max_length=32)
    sku: Optional[str] = Field(default=None, max_length=80)
    ativo: Optional[bool] = None
