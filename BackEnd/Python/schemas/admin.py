from pydantic import BaseModel, Field


class AdminUsuarioUpdate(BaseModel):
    papel: str | None = Field(default=None, pattern="^(usuario|parceiro|admin)$")
    ativo: bool | None = None


class AdminEstabelecimentoUpdate(BaseModel):
    parceiro_verificado: bool | None = None
    ativo: bool | None = None
