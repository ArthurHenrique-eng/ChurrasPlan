"""Carrega catálogo e preços de referência para desenvolvimento/E2E.

O planejador já possui fallback de preços de referência Brasil 2026 quando não
há oferta real. Este seed existe para cenários locais/E2E que também precisam
de registros de preço persistidos no banco. Não representa oferta comercial.
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
from services.precos_referencia import PRECOS_REFERENCIA_BRASIL

CATEGORIAS = {
    "carne": "Carnes",
    "bebida": "Bebidas",
    "extra": "Extras",
    "acompanhamento": "Acompanhamentos",
}

PRECOS_DEMO = dict(PRECOS_REFERENCIA_BRASIL)


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
                    Preco.fonte == "referencia-brasil-2026",
                )
                .first()
            )
            if not preco:
                preco = Preco(
                    produto_id=produto.id,
                    estabelecimento_id=estabelecimento.id,
                    fonte="referencia-brasil-2026",
                    origem="referencia_planejamento",
                )
                db.add(preco)
                criados += 1
            preco.preco = Decimal(str(valor)).quantize(Decimal("0.01"))
            preco.moeda = "BRL"
            preco.estoque_status = "disponivel"
            preco.disponivel = True

        db.commit()
        print(f"Seed demo concluído: {len(produtos)} produtos; {criados} preços demo criados/atualizados.")
        print("ATENÇÃO: valores de referência para planejamento; não são ofertas comerciais nem preços garantidos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
