from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class ConviteOut(BaseModel):
    codigo: str
    url: str
    churrasco_id: int
    nome_churrasco: str | None
    data_evento: datetime | None
    ativo: bool
    total_respostas: int = 0


class ConvitePublicoOut(BaseModel):
    codigo: str
    nome_churrasco: str | None
    data_evento: datetime | None
    tipo_evento: str
    duracao_horas: float
    organizador: str | None = None


class RespostaConviteIn(BaseModel):
    # Chave idempotente opcional. O frontend a cria antes do primeiro envio para
    # que retries de rede atualizem a mesma resposta em vez de duplicá-la.
    chave_resposta: str | None = Field(default=None, min_length=16, max_length=64)
    nome: str = Field(min_length=2, max_length=120)
    resposta: str
    tipo_convidado: str = "adulto"
    consome_alcool: bool = False
    vegetariano: bool = False
    vegano: bool = False
    sem_carne_bovina: bool = False
    sem_carne_suina: bool = False
    intolerante_lactose: bool = False
    alergias: str | None = Field(default=None, max_length=2000)
    outras_restricoes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validar(self):
        if self.resposta not in {"confirmado", "talvez", "nao"}:
            raise ValueError("resposta deve ser confirmado, talvez ou nao")
        if self.tipo_convidado not in {"adulto", "crianca"}:
            raise ValueError("tipo_convidado deve ser adulto ou crianca")
        if self.tipo_convidado == "crianca":
            self.consome_alcool = False
        if self.vegano:
            self.vegetariano = False
        return self


class RespostaConviteOut(BaseModel):
    id: int
    # Só é devolvida ao próprio convidado nas rotas públicas de resposta.
    # No resumo do organizador fica nula para não expor o segredo de edição.
    chave_resposta: str | None = None
    nome: str
    resposta: str
    tipo_convidado: str
    consome_alcool: bool
    vegetariano: bool
    vegano: bool
    sem_carne_bovina: bool
    sem_carne_suina: bool
    intolerante_lactose: bool
    alergias: str | None
    outras_restricoes: str | None


class ResumoConviteOut(BaseModel):
    churrasco_id: int
    confirmados: int
    talvez: int
    nao: int
    total_respostas: int
    adultos_confirmados: int
    criancas_confirmadas: int
    consumidores_alcool_confirmados: int
    vegetarianos_confirmados: int
    veganos_confirmados: int
    sem_carne_bovina_confirmados: int
    sem_carne_suina_confirmados: int
    intolerantes_lactose_confirmados: int
    respostas: list[RespostaConviteOut]
