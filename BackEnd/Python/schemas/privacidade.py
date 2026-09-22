from pydantic import BaseModel, Field


class ExclusaoContaIn(BaseModel):
    senha: str = Field(min_length=8, max_length=128)
    confirmacao: str = Field(min_length=7, max_length=20)


class ConsentimentoOut(BaseModel):
    tipo: str
    versao: str
    concedido: bool
    origem: str


class PreferenciaMarketingIn(BaseModel):
    concedido: bool
