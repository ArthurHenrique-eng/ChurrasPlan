"""Resolução de produto e conversão para compra usando catálogo real/fallback."""
from dataclasses import dataclass
from decimal import Decimal
import re
import unicodedata

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import CATALOGO_PRODUTOS_PADRAO
from models import Produto
from services.utils_calculo import ItemQuantidade, converter_para_compra


@dataclass
class ProdutoComercial:
    id: int | None
    slug: str
    nome: str
    categoria: str
    unidade_consumo: str
    unidade_venda: str
    venda_fracionada: bool
    incremento_venda: float | None
    quantidade_embalagem: float | None
    unidade_embalagem: str | None


def slugificar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def _fallback(slug: str, nome: str | None = None, categoria: str = "outro") -> ProdutoComercial:
    dados = CATALOGO_PRODUTOS_PADRAO.get(slug)
    if dados:
        return ProdutoComercial(
            id=None, slug=dados["slug"], nome=dados["nome"], categoria=dados["categoria"],
            unidade_consumo=dados["unidade_consumo"], unidade_venda=dados["unidade_venda"],
            venda_fracionada=dados["venda_fracionada"], incremento_venda=dados["incremento_venda"],
            quantidade_embalagem=dados["quantidade_embalagem"], unidade_embalagem=dados["unidade_embalagem"],
        )
    return ProdutoComercial(
        id=None, slug=slug, nome=nome or slug.replace("-", " ").title(), categoria=categoria,
        unidade_consumo="unidade", unidade_venda="unidade", venda_fracionada=False,
        incremento_venda=None, quantidade_embalagem=1.0, unidade_embalagem="unidade",
    )


def resolver_produto(db: Session | None, *, slug: str | None = None, nome: str | None = None, categoria: str = "outro") -> ProdutoComercial:
    slug_final = slug or slugificar(nome or "item")
    produto = None
    if db is not None:
        produto = db.query(Produto).filter(Produto.slug == slug_final, Produto.ativo.is_(True)).first()
        if not produto and nome:
            produto = db.query(Produto).filter(func.lower(Produto.nome) == nome.lower(), Produto.ativo.is_(True)).first()
    if not produto:
        return _fallback(slug_final, nome, categoria)
    return ProdutoComercial(
        id=produto.id, slug=produto.slug, nome=produto.nome,
        categoria=produto.categoria.tipo if produto.categoria else categoria,
        unidade_consumo=produto.unidade_consumo, unidade_venda=produto.unidade_venda,
        venda_fracionada=produto.venda_fracionada,
        incremento_venda=float(produto.incremento_venda) if produto.incremento_venda is not None else None,
        quantidade_embalagem=float(produto.quantidade_embalagem) if produto.quantidade_embalagem is not None else None,
        unidade_embalagem=produto.unidade_embalagem,
    )


def converter_produto(produto: ProdutoComercial, necessario: float) -> ItemQuantidade:
    return converter_para_compra(
        necessario,
        unidade_consumo=produto.unidade_consumo,
        unidade_venda=produto.unidade_venda,
        venda_fracionada=produto.venda_fracionada,
        incremento_venda=produto.incremento_venda,
        tamanho_embalagem=produto.quantidade_embalagem,
        unidade_embalagem=produto.unidade_embalagem,
    )
