"""
Regras de calculo de produtos extras e acompanhamentos (secoes 13/14 do
briefing + secao 15 da especificacao matematica).
Cada extra/acompanhamento so aparece no resultado se estiver na lista de
"ativos" enviada pelo frontend (o usuario escolheu usar aquele item).

Descartaveis contados por pessoa (copos, pratos, talheres, guardanapos,
palitos) recebem margem de seguranca de 10% antes do arredondamento para
cima (secao 15 da spec: N_compra = ceil(pessoas * fator * 1.10)), para
cobrir quebras/uso extra sem deixar o evento sem material.
"""
import math

from config import REGRAS_PADRAO


def calcular_extras(pessoas_total: int, carne_total_kg: float,
                     extras_ativos: list[str], regras: dict | None = None) -> dict:
    regras = regras or REGRAS_PADRAO["extras"]
    margem = regras["margem_seguranca"]
    resultado = {}

    if "sal_grosso" in extras_ativos:
        resultado["sal_grosso_kg"] = round(carne_total_kg * regras["sal_grosso_kg_por_kg_carne"], 2)
    if "copos" in extras_ativos:
        resultado["copos_unidades"] = math.ceil(pessoas_total * regras["copos_por_pessoa"] * margem)
    if "pratos" in extras_ativos:
        resultado["pratos_unidades"] = math.ceil(pessoas_total * regras["pratos_por_pessoa"] * margem)
    if "talheres" in extras_ativos:
        resultado["talheres_unidades"] = math.ceil(pessoas_total * regras["talheres_por_pessoa"] * margem)
    if "guardanapos" in extras_ativos:
        resultado["guardanapos_unidades"] = math.ceil(pessoas_total * regras["guardanapos_por_pessoa"] * margem)
    if "sacos_lixo" in extras_ativos:
        resultado["sacos_lixo_unidades"] = math.ceil(pessoas_total / regras["sacos_lixo_a_cada_pessoas"])
    if "acendedor" in extras_ativos:
        resultado["acendedor_unidades"] = regras["acendedor_unidades"]
    if "fosforo_isqueiro" in extras_ativos:
        resultado["fosforo_isqueiro_unidades"] = regras["fosforo_isqueiro_unidades"]
    if "papel_toalha" in extras_ativos:
        resultado["papel_toalha_rolos"] = math.ceil(pessoas_total / regras["papel_toalha_rolos_a_cada_pessoas"])
    if "papel_aluminio" in extras_ativos:
        resultado["papel_aluminio_rolos"] = math.ceil(pessoas_total / regras["papel_aluminio_rolos_a_cada_pessoas"])
    if "palitos" in extras_ativos:
        resultado["palitos_unidades"] = math.ceil(pessoas_total * regras["palitos_unidades_por_pessoa"] * margem)

    return resultado


def calcular_acompanhamentos(pessoas_total: int, acompanhamentos_ativos: list[str],
                              regras: dict | None = None) -> dict:
    regras = regras or REGRAS_PADRAO["acompanhamentos"]
    resultado = {}

    mapa_gramas = {
        "farofa": "farofa_g_por_pessoa",
        "vinagrete": "vinagrete_g_por_pessoa",
        "queijo_coalho": "queijo_coalho_g_por_pessoa",
        "maionese": "maionese_g_por_pessoa",
        "salada": "salada_g_por_pessoa",
        "arroz": "arroz_g_por_pessoa",
        "pao": "pao_g_por_pessoa",
    }
    for item, chave_regra in mapa_gramas.items():
        if item in acompanhamentos_ativos:
            gramas = pessoas_total * regras[chave_regra]
            resultado[f"{item}_kg"] = round(gramas / 1000, 2)

    if "pao_de_alho" in acompanhamentos_ativos:
        resultado["pao_de_alho_unidades"] = math.ceil(
            pessoas_total * regras["pao_de_alho_unidades_por_pessoa"]
        )
    if "molhos" in acompanhamentos_ativos:
        resultado["molhos_litros"] = round(
            pessoas_total * regras["molhos_ml_por_pessoa"] / 1000, 2
        )

    return resultado
