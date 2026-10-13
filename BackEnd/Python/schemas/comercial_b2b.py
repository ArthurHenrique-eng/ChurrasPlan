"""Entradas de catálogo em massa e campanhas com revisão humana."""
from datetime import UTC, datetime, timedelta
from pydantic import BaseModel, Field, field_validator, model_validator


class CatalogoCSV(BaseModel):
    chave_idempotencia: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$")
    csv_texto: str = Field(min_length=15, max_length=100000)


class CampanhaCriar(BaseModel):
    codigo: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,59}$")
    nome: str = Field(min_length=3, max_length=150)
    descricao: str | None = Field(default=None, max_length=500)
    inicio_em: datetime
    fim_em: datetime
    preco_ids: list[int] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validar_datas(self):
        inicio = self.inicio_em.replace(tzinfo=UTC) if self.inicio_em.tzinfo is None else self.inicio_em.astimezone(UTC)
        fim = self.fim_em.replace(tzinfo=UTC) if self.fim_em.tzinfo is None else self.fim_em.astimezone(UTC)
        if fim <= inicio or fim - inicio > timedelta(days=90):
            raise ValueError("Campanha deve durar entre 1 instante e 90 dias.")
        if inicio < datetime.now(UTC) - timedelta(days=1):
            raise ValueError("Campanha não pode começar no passado.")
        if len(set(self.preco_ids)) != len(self.preco_ids) or any(x <= 0 for x in self.preco_ids):
            raise ValueError("Identificadores de ofertas devem ser distintos e positivos.")
        self.inicio_em = inicio.replace(tzinfo=None)
        self.fim_em = fim.replace(tzinfo=None)
        return self


class CampanhaRevisao(BaseModel):
    aprovar: bool
    motivo: str | None = Field(default=None, max_length=400)

    @model_validator(mode="after")
    def validar_motivo(self):
        if not self.aprovar and (not self.motivo or len(self.motivo.strip()) < 8):
            raise ValueError("Informe o motivo da rejeição (mínimo 8 caracteres).")
        return self
