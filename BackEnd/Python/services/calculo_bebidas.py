from config import REGRAS_PADRAO
from services.catalogo_produtos import resolver_produto, converter_produto
from services.utils_calculo import fator_por_faixa


def _fator_evento(tipo_evento: str) -> float:
    return REGRAS_PADRAO["evento"]["fatores"].get(tipo_evento, 1.0)


def calcular_bebidas_nao_alcoolicas(pessoas_total: int, perfil_consumo: str,
                                     bebidas_ativas: list[str],
                                     perfil_personalizado: dict | None = None,
                                     tipo_evento: str = "outro",
                                     regras: dict | None = None) -> dict:
    regras = regras or REGRAS_PADRAO["bebida_nao_alcoolica"]
    fator_perfil = REGRAS_PADRAO["perfil"]["fatores"].get(perfil_consumo, 1.0)
    fator_evento = _fator_evento(tipo_evento)
    resultado = {}
    for bebida in bebidas_ativas:
        if bebida not in regras["litros_por_pessoa_base"]:
            continue
        if perfil_consumo == "personalizado" and perfil_personalizado:
            litros_pessoa = perfil_personalizado.get(
                f"{bebida}_litros_pessoa", regras["litros_por_pessoa_base"][bebida]
            )
        else:
            litros_pessoa = regras["litros_por_pessoa_base"][bebida] * fator_perfil
        resultado[bebida] = round(pessoas_total * litros_pessoa * fator_evento, 3)
    return resultado


def calcular_bebida_alcoolica(adultos_que_bebem: int, duracao_horas: float,
                               perfil_consumo: str,
                               perfil_personalizado: dict | None = None,
                               tipo_evento: str = "outro",
                               regras: dict | None = None) -> dict:
    regras = regras or REGRAS_PADRAO["bebida_alcoolica"]
    fator_perfil = REGRAS_PADRAO["perfil"]["fatores"].get(perfil_consumo, 1.0)
    if perfil_consumo == "personalizado" and perfil_personalizado:
        litros_hora = perfil_personalizado.get(
            "cerveja_litros_consumidor_hora", regras["litros_por_consumidor_hora"]
        )
    else:
        litros_hora = regras["litros_por_consumidor_hora"] * fator_perfil
    litros_total = round(adultos_que_bebem * litros_hora * duracao_horas * _fator_evento(tipo_evento), 3)
    return {"litros_total": litros_total}


def calcular_gelo(pessoas_total: int, duracao_horas: float, perfil_consumo: str,
                   perfil_personalizado: dict | None = None,
                   gelo_ativo: bool = False,
                   regras: dict | None = None) -> float:
    if not gelo_ativo:
        return 0.0
    regras = regras or REGRAS_PADRAO["gelo"]
    fator_duracao = fator_por_faixa(duracao_horas, regras["faixas_duracao"])
    if perfil_consumo == "personalizado" and perfil_personalizado:
        kg_por_pessoa = perfil_personalizado.get("gelo_kg_pessoa", regras["kg_por_pessoa_base"])
    else:
        kg_por_pessoa = regras["kg_por_pessoa_base"]
    return round(pessoas_total * kg_por_pessoa * fator_duracao, 3)


def converter_bebida_para_compra(slug: str, necessario: float, db=None):
    produto = resolver_produto(db, slug=slug, categoria="bebida")
    return produto, converter_produto(produto, necessario)
