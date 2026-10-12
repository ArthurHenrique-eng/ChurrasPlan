"""Assistência opcional. Extração local e contrato de provedor testável, sem chamadas pagas.

Um adaptador de LLM só pode ser ativado após escolha do provedor, credencial e
orçamento aprovados. Não há acesso a DB, pagamentos, ferramentas ou mutações.
"""
import re
from decimal import Decimal
from typing import Protocol, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationError
from services.calculo_carne import calcular_quantidade_total_carne


class ParametrosAssistente(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    adultos: int = Field(ge=0, le=500)
    criancas: int = Field(default=0, ge=0, le=500)
    adultos_bebem_alcool: int = Field(default=0, ge=0, le=500)
    duracao_horas: float = Field(default=4.0, ge=1, le=48)
    orcamento_maximo: Decimal | None = Field(default=None, ge=0, le=10000000)
    tipo_evento: Literal["almoco", "jantar", "aniversario", "confraternizacao_empresa", "outro"] = "almoco"
    perfil_consumo: Literal["leve", "normal", "alto"] = "normal"

    @model_validator(mode="after")
    def total_valido(self):
        if not 1 <= self.adultos + self.criancas <= 500 or self.adultos_bebem_alcool > self.adultos:
            raise ValueError("Participantes ou consumo de álcool inconsistentes")
        return self


class ProvedorAssistente(Protocol):
    """Implementações futuras exigem timeout <=5s, limite de tokens/custo e JSON estrito."""
    def extrair(self, texto_minimo: str) -> dict: ...


def extrair_local(texto: str) -> ParametrosAssistente:
    texto = texto.lower()
    total = re.search(r"(\d+)\s*(?:pessoas|convidados)", texto)
    adultos = re.search(r"(\d+)\s*adultos", texto)
    criancas = re.search(r"(\d+)\s*crian[çc]as", texto)
    kids = int(criancas.group(1)) if criancas else 0
    if total:
        adults = int(total.group(1)) - kids
    elif adultos:
        adults = int(adultos.group(1))
    else:
        raise ValueError("Informe quantas pessoas ou adultos participarão e quantas são crianças.")
    duracao = re.search(r"(\d+(?:[.,]\d+)?)\s*horas", texto)
    orcamento = re.search(r"(?:r\$\s*|or[çc]amento\s*(?:de\s*)?)(\d[\d.,]*)", texto)
    valor = None
    if orcamento:
        bruto = orcamento.group(1).rstrip(".,")
        if "," in bruto or re.fullmatch(r"\d{1,3}(?:\.\d{3})+", bruto):
            bruto = bruto.replace(".", "").replace(",", ".")
        valor = Decimal(bruto)
    tipo = "aniversario" if "anivers" in texto else "confraternizacao_empresa" if any(x in texto for x in ["empresa", "corporativo"]) else "jantar" if "jantar" in texto else "almoco"
    perfil = "leve" if "econômico" in texto or "economico" in texto else "alto" if "generoso" in texto else "normal"
    return ParametrosAssistente(adultos=adults, criancas=kids, duracao_horas=float(duracao.group(1).replace(",", ".")) if duracao else 4.0,
        orcamento_maximo=valor, tipo_evento=tipo, perfil_consumo=perfil)


def assistir(texto: str, *, provedor: ProvedorAssistente | None = None) -> dict:
    # Minimização: envie ao adaptador somente parâmetros locais reconhecidos,
    # jamais nomes, e-mails, restrições sensíveis ou o prompt original.
    local = extrair_local(texto)
    parametros, fonte = local, "extracao_local"
    if provedor is not None:
        try:
            candidato = provedor.extrair(local.model_dump_json())
            parametros = ParametrosAssistente.model_validate(candidato)
            fonte = "provedor_simulado"
        except (ValidationError, ValueError, TypeError, TimeoutError, OSError):
            parametros = local
    carne = calcular_quantidade_total_carne(parametros.adultos, 0, parametros.criancas,
        parametros.duracao_horas, parametros.perfil_consumo, tipo_evento=parametros.tipo_evento)
    return {"parametros": parametros.model_dump(mode="json"), "fonte": fonte,
            "necessidade_carne_total_kg": carne["total_kg"], "custo_provedor_centavos": 0,
            "exige_confirmacao": True,
            "avisos": ["Revise participantes, perfil, duração e orçamento antes de aplicar.",
                        "O motor determinístico calcula as quantidades. Esta sugestão não salva um evento nem realiza compras.",
                        "Não envie nomes, contatos ou informações sensíveis. A versão atual usa extração local, sem LLM externo."]}
