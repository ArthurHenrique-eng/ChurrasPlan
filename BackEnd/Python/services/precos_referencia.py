"""Preços de referência para planejamento quando não há oferta real cadastrada.

Os valores são estimativas nacionais de varejo para setembro/2026. Eles não
representam uma oferta de estabelecimento e nunca participam do ranking de
mercados. Servem somente para que o planejamento tenha uma ordem de grandeza
de custo até existirem preços reais/verificados para o item.

A calibração combina pesquisas públicas de PROCON para churrasco em 2026,
levantamento Neogrid de maio/2026 e amostras de varejo nacional. Como preços
variam por cidade, marca, promoção e embalagem, o frontend deve apresentar
estes valores como "referência estimada", nunca como preço atual garantido.
"""
from __future__ import annotations

REFERENCIA_PRECOS_VERSAO = "BR-2026-09"
REFERENCIA_PRECOS_ATUALIZADA_EM = "2026-09"

# Para venda fracionada, o valor é por unidade_venda (normalmente kg).
# Para venda fechada, o valor é por embalagem comercial definida no catálogo.
PRECOS_REFERENCIA_BRASIL: dict[str, float] = {
    # Carnes — R$/kg
    "picanha": 84.90,
    "picanha-suina": 36.90,
    "contra-file": 57.90,
    "alcatra": 54.90,
    "fraldinha": 49.90,
    "maminha": 59.90,
    "acem": 35.90,
    "costela": 29.90,
    "costelinha-porco": 23.90,
    "cupim": 45.90,
    "linguica": 24.90,
    "lombo": 25.90,
    "bisteca": 18.90,
    "frango": 13.90,
    "asinha-frango": 15.90,
    "coracao": 31.90,
    "queijo-coalho-churrasco": 49.90,
    "pao-alho-churrasco": 29.90,
    "bife-ancho": 74.90,
    "bife-chorizo": 69.90,
    "prime-rib": 89.90,
    "short-rib": 59.90,
    "file-mignon": 104.90,

    # Bebidas e apoio — por embalagem do catálogo
    "carvao": 21.90,          # saco 3 kg
    "agua": 3.99,             # garrafa 1,5 L
    "refrigerante": 10.49,    # garrafa 2 L
    "suco": 8.99,             # caixa 1 L
    "cerveja": 4.79,          # lata 350 ml
    "gelo": 15.90,            # saco 5 kg

    # Extras — por embalagem/unidade do catálogo
    "sal-grosso": 3.49,       # pacote 1 kg
    "acendedor": 9.90,
    "fosforo-isqueiro": 5.90,
    "copos": 8.99,            # pacote 50
    "pratos": 8.99,           # pacote 10
    "talheres": 9.99,         # pacote 20
    "guardanapos": 8.49,      # pacote 50
    "sacos-lixo": 12.90,      # pacote 10
    "papel-toalha": 8.99,     # pacote 2 rolos
    "papel-aluminio": 10.99,  # 1 rolo
    "palitos": 4.99,           # caixa 100

    # Acompanhamentos — por embalagem/unidade do catálogo
    "pao-de-alho": 11.49,     # pacote 5 unidades
    "farofa": 7.49,           # pacote 500 g
    "vinagrete": 14.90,       # R$/kg
    "queijo-coalho": 24.90,   # pacote 500 g
    "maionese": 8.99,         # pote 500 g
    "salada": 15.90,          # R$/kg
    "arroz": 6.99,            # pacote 1 kg
    "molhos": 6.99,           # frasco 250 ml
    "pao": 16.90,             # R$/kg
}


# Compatibilidade com planejamentos criados quando o catálogo ampliado de
# parceiros ainda possuía produtos genéricos com slugs diferentes dos usados
# pelo planejador. Frango e linguiça podiam ficar persistidos com estes slugs,
# embora representassem os mesmos itens de referência.
ALIASES_PRECOS_REFERENCIA: dict[str, str] = {
    "frango-generico": "frango",
    "linguica-generica": "linguica",
}


def obter_preco_referencia(slug: str | None) -> float | None:
    if not slug:
        return None
    slug_canonico = ALIASES_PRECOS_REFERENCIA.get(slug, slug)
    return PRECOS_REFERENCIA_BRASIL.get(slug_canonico)
