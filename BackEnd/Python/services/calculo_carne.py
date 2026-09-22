from config import REGRAS_PADRAO
from services.catalogo_produtos import resolver_produto, converter_produto, slugificar
from services.utils_calculo import fator_por_faixa


def _coeficientes_carne(perfil_consumo: str, perfil_personalizado: dict | None,
                         regras_carne: dict, regras_perfil: dict) -> tuple[float, float]:
    if perfil_consumo == "personalizado":
        if not perfil_personalizado:
            raise ValueError("Perfil personalizado selecionado, mas nenhum parâmetro foi informado.")
        return (
            perfil_personalizado.get("carne_adulto_kg", regras_carne["kg_por_adulto_base"]),
            perfil_personalizado.get("carne_crianca_kg", regras_carne["kg_por_crianca_base"]),
        )
    if perfil_consumo not in regras_perfil["fatores"]:
        raise ValueError(f"perfil_consumo inválido: '{perfil_consumo}'")
    fator = regras_perfil["fatores"][perfil_consumo]
    return regras_carne["kg_por_adulto_base"] * fator, regras_carne["kg_por_crianca_base"] * fator


def calcular_quantidade_total_carne(homens: int, mulheres: int, criancas: int,
                                     duracao_horas: float, perfil_consumo: str,
                                     perfil_personalizado: dict | None = None,
                                     tipo_evento: str = "outro",
                                     regras: dict | None = None) -> dict:
    regras_carne = regras or REGRAS_PADRAO["carne"]
    kg_adulto, kg_crianca = _coeficientes_carne(
        perfil_consumo, perfil_personalizado, regras_carne, REGRAS_PADRAO["perfil"]
    )
    fator_duracao = fator_por_faixa(duracao_horas, regras_carne["faixas_duracao"])
    fator_evento = REGRAS_PADRAO["evento"]["fatores"].get(tipo_evento, 1.0)
    base = (homens + mulheres) * kg_adulto + criancas * kg_crianca
    total_kg = round(base * fator_duracao * fator_evento, 3)
    return {
        "total_kg": total_kg,
        "adultos": homens + mulheres,
        "criancas": criancas,
        "fator_duracao": round(fator_duracao, 3),
        "fator_evento": round(fator_evento, 3),
    }


def distribuir_carnes(total_kg: float, carnes_selecionadas: list[dict], db=None) -> list[dict]:
    if not carnes_selecionadas:
        raise ValueError("Selecione ao menos uma carne.")
    soma = sum(float(c["percentual"]) for c in carnes_selecionadas)
    if abs(soma - 100) > 0.01:
        raise ValueError(f"A soma dos percentuais das carnes deve ser 100%. Valor atual: {soma:.2f}%")

    resultado = []
    for c in carnes_selecionadas:
        necessario = round(total_kg * float(c["percentual"]) / 100, 3)
        slug = c.get("produto_slug") or slugificar(c["nome"])
        produto = resolver_produto(db, slug=slug, nome=c["nome"], categoria="carne")
        compra = converter_produto(produto, necessario)
        resultado.append({
            "nome": produto.nome,
            "produto_slug": produto.slug,
            "produto_id": produto.id,
            "percentual": float(c["percentual"]),
            "quantidade_kg": compra.necessario,
            "quantidade_compra_kg": compra.compra,
            "quantidade_embalagens": compra.embalagens,
            "unidade_venda": produto.unidade_venda,
            "produto": produto,
            "compra": compra,
        })
    return resultado


def calcular_carvao(carne_total_kg: float, duracao_horas: float,
                     carvao_ativo: bool = True,
                     perfil_personalizado: dict | None = None,
                     perfil_consumo: str = "normal",
                     db=None,
                     regras: dict | None = None) -> dict:
    regras = regras or REGRAS_PADRAO["carvao"]
    if not carvao_ativo:
        return {"necessario_kg": 0.0, "compra_kg": 0.0, "sacos": 0, "produto": None, "compra": None}
    coef = regras["kg_por_kg_carne"]
    if perfil_consumo == "personalizado" and perfil_personalizado:
        coef = perfil_personalizado.get("carvao_kg_por_kg_carne", coef)
    necessario = round(carne_total_kg * coef, 3)
    produto = resolver_produto(db, slug="carvao", nome="Carvão", categoria="extra")
    compra = converter_produto(produto, necessario)
    return {
        "necessario_kg": compra.necessario,
        "compra_kg": compra.compra,
        "sacos": compra.embalagens or 0,
        "produto": produto,
        "compra": compra,
    }
