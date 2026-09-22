from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegistroUsuarioIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160)
    senha: str = Field(min_length=10, max_length=128)
    aceite_termos: bool = False
    aceite_privacidade: bool = False
    aceite_marketing: bool = False

    @field_validator("email")
    @classmethod
    def normaliza_email(cls, v):
        return v.strip().lower()


class LoginIn(BaseModel):
    email: str
    senha: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    papel: str
    plano: str
    ativo: bool
    email_verificado_em: datetime | None = None
    criado_em: datetime


class AuthOut(BaseModel):
    usuario: UsuarioOut
    mensagem: str
    dev_verification_token: str | None = None


class VerificarEmailIn(BaseModel):
    token: str = Field(min_length=20)


class EsqueciSenhaIn(BaseModel):
    email: str


class RedefinirSenhaIn(BaseModel):
    token: str = Field(min_length=20)
    nova_senha: str = Field(min_length=10, max_length=128)


class MensagemOut(BaseModel):
    mensagem: str
    dev_token: str | None = None
