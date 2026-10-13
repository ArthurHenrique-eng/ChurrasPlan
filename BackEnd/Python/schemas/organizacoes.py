"""Entradas explicitamente limitadas a papéis B2B reconhecidos."""
from typing import Literal
from pydantic import BaseModel, Field

PapelOrganizacao = Literal["proprietario", "gestor", "editor", "leitor"]


class ConviteOrganizacaoCreate(BaseModel):
    email: str = Field(min_length=5, max_length=160)
    papel: PapelOrganizacao


class ConviteOrganizacaoAceitar(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class AtualizarPapelMembro(BaseModel):
    papel: PapelOrganizacao
