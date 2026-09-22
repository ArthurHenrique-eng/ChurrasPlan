"""
Validacoes reutilizaveis, aplicadas no backend (nunca so no frontend, conforme
secao 27 do briefing: "Nenhuma regra importante deverá depender exclusivamente
do JavaScript do frontend"). O FastAPI + Pydantic ja cobre boa parte via
schemas (Field(ge=0), Literal, field_validator), estas funcoes cobrem regras
que envolvem mais de um campo ou que sao reaproveitadas em varios lugares.
"""


def validar_soma_percentuais(itens: list[dict], chave_percentual: str = "percentual",
                              tolerancia: float = 0.01) -> None:
    soma = sum(i[chave_percentual] for i in itens)
    if abs(soma - 100) > tolerancia:
        raise ValueError(f"A soma dos percentuais deve ser 100%. Valor atual: {soma:.2f}%")


def validar_nao_negativo(valor: float, nome_campo: str) -> None:
    if valor < 0:
        raise ValueError(f"{nome_campo} não pode ser negativo")


CHAVES_PERFIL_PERSONALIZADO = {
    "carne_adulto_kg", "carne_crianca_kg", "agua_litros_pessoa",
    "refrigerante_litros_pessoa", "suco_litros_pessoa",
    "cerveja_litros_consumidor_hora", "gelo_kg_pessoa", "carvao_kg_por_kg_carne",
}


def validar_perfil_personalizado(perfil_consumo: str, perfil_personalizado: dict | None) -> None:
    """
    Regra de negocio (secao 7 do briefing + secao 31 da spec): se o perfil
    escolhido for "personalizado", os coeficientes sao obrigatorios e devem
    ser numeros nao-negativos, dentro das chaves conhecidas. Nunca confiar
    apenas na validacao do formulario do frontend.
    """
    if perfil_consumo != "personalizado":
        return
    if not perfil_personalizado:
        raise ValueError(
            "Perfil personalizado exige o campo 'perfil_personalizado' com ao menos um coeficiente."
        )
    for chave, valor in perfil_personalizado.items():
        if chave not in CHAVES_PERFIL_PERSONALIZADO:
            raise ValueError(
                f"Coeficiente de perfil personalizado desconhecido: '{chave}'. "
                f"Use um de: {sorted(CHAVES_PERFIL_PERSONALIZADO)}"
            )
        if not isinstance(valor, (int, float)) or valor < 0:
            raise ValueError(f"O coeficiente '{chave}' deve ser um número não-negativo.")
