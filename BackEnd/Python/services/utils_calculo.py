"""Helpers para separar necessidade física, compra comercial e embalagem."""
import math
from dataclasses import dataclass


def fator_por_faixa(duracao_horas: float, faixas: list[tuple[float, float]]) -> float:
    if duracao_horas <= 0:
        raise ValueError("duracao_horas deve ser maior que zero")
    for limite_superior, fator in faixas:
        if duracao_horas <= limite_superior:
            return fator
    return faixas[-1][1]


@dataclass
class ItemQuantidade:
    necessario: float
    unidade_consumo: str
    compra: float
    unidade_compra: str
    tamanho_embalagem: float | None = None
    unidade_embalagem: str | None = None
    embalagens: int | None = None
    venda_fracionada: bool = False


def converter_para_compra(
    necessario: float,
    *,
    unidade_consumo: str,
    unidade_venda: str,
    venda_fracionada: bool = False,
    incremento_venda: float | None = None,
    tamanho_embalagem: float | None = None,
    unidade_embalagem: str | None = None,
) -> ItemQuantidade:
    """Converte necessidade para a forma comercial do produto.

    - venda fracionada: arredonda para o incremento comercial (ex. 0,1 kg);
    - embalagem fechada: arredonda o número de embalagens para cima.
    """
    necessario = max(0.0, float(necessario))
    if venda_fracionada:
        incremento = float(incremento_venda or 0.01)
        if incremento <= 0:
            raise ValueError("incremento_venda deve ser maior que zero")
        unidades = math.ceil(round(necessario / incremento, 9)) if necessario > 0 else 0
        compra = round(unidades * incremento, 3)
        return ItemQuantidade(
            necessario=round(necessario, 3), unidade_consumo=unidade_consumo,
            compra=compra, unidade_compra=unidade_consumo,
            venda_fracionada=True,
        )

    tamanho = float(tamanho_embalagem or 1.0)
    if tamanho <= 0:
        raise ValueError("tamanho_embalagem deve ser maior que zero")
    embalagens = math.ceil(round(necessario / tamanho, 9)) if necessario > 0 else 0
    compra = round(embalagens * tamanho, 3)
    return ItemQuantidade(
        necessario=round(necessario, 3), unidade_consumo=unidade_consumo,
        compra=compra, unidade_compra=unidade_consumo,
        tamanho_embalagem=tamanho, unidade_embalagem=unidade_embalagem or unidade_consumo,
        embalagens=embalagens, venda_fracionada=False,
    )
