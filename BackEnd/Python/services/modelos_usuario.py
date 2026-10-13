"""Snapshot de configurações de um churrasco para modelos reutilizáveis."""
from __future__ import annotations


def snapshot_modelo(churrasco) -> dict:
    return {
        "tipo_evento": churrasco.tipo_evento,
        "duracao_horas": churrasco.duracao_horas,
        "perfil_consumo": churrasco.perfil_consumo,
        "perfil_personalizado": churrasco.perfil_personalizado,
        "adultos": churrasco.total_adultos,
        "adultos_bebem_alcool": churrasco.total_adultos_bebem,
        "criancas": churrasco.criancas,
        "vegetarianos": churrasco.vegetarianos,
        "veganos": churrasco.veganos,
        "sem_carne_bovina": churrasco.sem_carne_bovina,
        "sem_carne_suina": churrasco.sem_carne_suina,
        "intolerantes_lactose": churrasco.intolerantes_lactose,
        "alergias": churrasco.alergias,
        "outras_restricoes": churrasco.outras_restricoes,
        "orcamento_maximo": float(churrasco.orcamento_maximo) if churrasco.orcamento_maximo is not None else None,
        "carnes": [
            {"nome": c.nome_item, "produto_slug": c.produto_slug, "percentual": float(c.percentual)}
            for c in churrasco.carnes
        ],
        "carvao_ativo": churrasco.carvao_ativo,
        "bebidas_nao_alcoolicas_ativas": [
            b.produto_slug for b in churrasco.bebidas if b.produto_slug not in {"cerveja", "gelo"}
        ],
        "bebida_alcoolica_ativa": any(b.produto_slug == "cerveja" for b in churrasco.bebidas),
        "gelo_ativo": churrasco.gelo_ativo,
        "extras_ativos": [
            e.produto_slug for e in churrasco.itens_extra if e.tipo == "extra" and e.produto_slug != "carvao"
        ],
        "acompanhamentos_ativos": [
            e.produto_slug for e in churrasco.itens_extra if e.tipo == "acompanhamento"
        ],
    }
