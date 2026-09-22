"""Carrega catálogo e preços DEMONSTRATIVOS para desenvolvimento/E2E.

Nunca é executado automaticamente em produção. Os valores não representam
preços reais e servem apenas para que orçamento, custo por pessoa e divisão
possam ser exercitados localmente antes das integrações com parceiros.
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

# Permite executar diretamente com `python scripts/seed_demo.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CATALOGO_PRODUTOS_PADRAO, settings
from database.connection import SessionLocal
from models import Categoria, Estabelecimento, Preco, Produto

CATEGORIAS = {
    "carne": "Carnes",
    "bebida": "Bebidas",
    "extra": "Extras",
    "acompanhamento": "Acompanhamentos",
}

PRECOS_DEMO = {
    "picanha": 54.90, "picanha-suina": 31.90, "contra-file": 44.90, "alcatra": 39.90,
    "fraldinha": 39.90, "maminha": 41.90, "acem": 29.90, "costela": 32.90,
    "costelinha-porco": 27.90, "cupim": 36.90, "linguica": 22.90, "lombo": 28.90,
    "bisteca": 24.90, "frango": 18.90, "asinha-frango": 17.90, "coracao": 34.90,
    "queijo-coalho-churrasco": 39.90, "pao-alho-churrasco": 22.90, "bife-ancho": 69.90,
    "bife-chorizo": 64.90, "prime-rib": 74.90, "short-rib": 58.90, "file-mignon": 79.90,
    "carvao": 18.00, "agua": 3.50, "refrigerante": 8.90, "suco": 7.90,
    "cerveja": 4.50, "gelo": 14.00, "sal-grosso": 6.50, "acendedor": 9.90,
    "fosforo-isqueiro": 4.90, "copos": 8.90, "pratos": 7.90, "talheres": 8.90,
    "guardanapos": 6.90, "sacos-lixo": 12.90, "papel-toalha": 8.90, "papel-aluminio": 11.90,
    "palitos": 4.90, "pao-de-alho": 12.90, "farofa": 9.90, "vinagrete": 18.90,
    "queijo-coalho": 19.90, "maionese": 9.90, "salada": 16.90, "arroz": 7.90,
    "molhos": 6.90, "pao": 14.90,
}


def main() -> None:
    if settings.APP_ENV == "production" and os.getenv("ALLOW_DEMO_SEED", "false").lower() not in {"1", "true", "yes"}:
        raise SystemExit("Seed demonstrativo bloqueado em produção. Use ofertas reais/verificadas.")

    db = SessionLocal()
    try:
        categorias = {}
        for tipo, nome in CATEGORIAS.items():
            categoria = db.query(Categoria).filter(Categoria.nome == nome).first()
            if not categoria:
                categoria = Categoria(nome=nome, tipo=tipo)
                db.add(categoria)
                db.flush()
            else:
                categoria.tipo = tipo
            categorias[tipo] = categoria

        produtos = {}
        for slug, dados in CATALOGO_PRODUTOS_PADRAO.items():
            produto = db.query(Produto).filter(Produto.slug == slug).first()
            if not produto:
                produto = Produto(slug=slug, categoria_id=categorias[dados["categoria"]].id)
                db.add(produto)
            produto.categoria_id = categorias[dados["categoria"]].id
            produto.tipo_produto = "generico"
            produto.nome = dados["nome"]
            produto.unidade_consumo = dados["unidade_consumo"]
            produto.unidade_venda = dados["unidade_venda"]
            produto.venda_fracionada = dados["venda_fracionada"]
            produto.incremento_venda = dados["incremento_venda"]
            produto.quantidade_embalagem = dados["quantidade_embalagem"]
            produto.unidade_embalagem = dados["unidade_embalagem"]
            produto.ativo = True
            db.flush()
            produtos[slug] = produto

        estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.slug == "mercado-demo-churrasplan").first()
        if not estabelecimento:
            estabelecimento = Estabelecimento(
                slug="mercado-demo-churrasplan",
                nome="Mercado Demo ChurrasPlan",
                tipo="supermercado",
                endereco="Dados demonstrativos — não é um estabelecimento real",
                ativo=True,
            )
            db.add(estabelecimento)
            db.flush()
        else:
            estabelecimento.ativo = True

        criados = 0
        for slug, valor in PRECOS_DEMO.items():
            produto = produtos.get(slug)
            if not produto:
                continue
            preco = (
                db.query(Preco)
                .filter(
                    Preco.produto_id == produto.id,
                    Preco.estabelecimento_id == estabelecimento.id,
                    Preco.fonte == "seed-demo-v3",
                )
                .first()
            )
            if not preco:
                preco = Preco(
                    produto_id=produto.id,
                    estabelecimento_id=estabelecimento.id,
                    fonte="seed-demo-v3",
                    origem="seed_demo",
                )
                db.add(preco)
                criados += 1
            preco.preco = Decimal(str(valor)).quantize(Decimal("0.01"))
            preco.moeda = "BRL"
            preco.estoque_status = "disponivel"
            preco.disponivel = True

        db.commit()
        print(f"Seed demo concluído: {len(produtos)} produtos; {criados} preços demo criados/atualizados.")
        print("ATENÇÃO: preços demonstrativos, não reais. Não use como informação comercial em produção.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
