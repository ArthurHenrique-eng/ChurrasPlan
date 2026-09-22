from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ListaComprasItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    produto_id: Optional[int] = None
    estabelecimento_compra_id: Optional[int] = None
    descricao: str
    quantidade: float
    unidade: str
    quantidade_embalagens: Optional[int] = None
    unidade_venda: str
    categoria: str
    preco_unitario: Optional[float] = None
    subtotal_estimado: Optional[float] = None
    valor_pago_total: Optional[float] = None
    comprado: bool
    comprado_em: Optional[datetime] = None


class ListaComprasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    churrasco_id: int
    itens: list[ListaComprasItemOut]
    total_estimado: Optional[float] = None
    estimativa_completa: bool = False
    itens_com_preco: int = 0
    itens_sem_preco: int = 0
    total_pago: float = 0
    valor_pago_completo: bool = False
    itens_com_valor_pago: int = 0
    economia_real: Optional[float] = None
    progresso_percentual: float = 0
    itens_comprados: int = 0
    itens_total: int = 0


class ListaComprasItemUpdate(BaseModel):
    comprado: bool
    valor_pago_total: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    estabelecimento_compra_id: Optional[int] = None
