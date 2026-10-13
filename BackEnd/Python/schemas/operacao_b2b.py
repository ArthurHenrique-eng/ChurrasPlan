"""Inputs operacionais B2B, sem moeda/vendas fictícias."""
from pydantic import BaseModel, Field


class FilialMetaUpdate(BaseModel):
    codigo_filial: str | None = Field(default=None, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
    unidade_matriz: bool = False
    ativo: bool = True


class ImportacaoOfertasCSV(BaseModel):
    chave_idempotencia: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$")
    csv_texto: str = Field(min_length=20, max_length=100000)
