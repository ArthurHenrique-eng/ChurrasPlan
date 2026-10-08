"""Catálogo B2B independente e referências distintas de ofertas reais."""
import pytest

from config import CATALOGO_PRODUTOS_PADRAO
from database.connection import get_db
from main import app
from models import Categoria, Produto
from services.precos_referencia import (
    PRECOS_REFERENCIA_BRASIL, REFERENCIA_PRECOS_ATUALIZADA_EM,
    obter_preco_referencia,
)
from tests.test_integracao_churrascos import client


def test_catalogo_generico_oferece_categorias_e_nao_depende_de_ofertas(client):
    resposta = client.get("/api/produtos/genericos")
    assert resposta.status_code == 200, resposta.text
    produtos = {p["slug"]: p for p in resposta.json()}
    assert {"picanha", "carvao", "agua", "cerveja"} <= produtos.keys()
    assert {p["categoria_nome"] for p in produtos.values()} >= {"Carnes", "Bebidas", "Extras"}
    assert produtos["agua"]["preco_referencia"] == pytest.approx(3.99)
    assert produtos["agua"]["preco_referencia_data_base"] == "2026-09"
    assert produtos["agua"]["preco_referencia_unidade"] == "garrafa"


def test_preco_referencia_catalogo_nao_altera_preco_real(client):
    r = client.get("/api/produtos?tipo_produto=generico")
    assert r.status_code == 200
    picanha = next(p for p in r.json() if p["slug"] == "picanha")
    assert picanha["preco_minimo_atual"] == pytest.approx(50.00)
    assert picanha["preco_referencia"] == pytest.approx(84.90)
    assert picanha["preco_referencia_unidade"] == "kg"
    detalhe = client.get(f"/api/produtos/{picanha['id']}")
    assert detalhe.status_code == 200
    assert detalhe.json()["preco_referencia_data_base"] == "2026-09"
    assert detalhe.json()["preco_minimo_atual"] == pytest.approx(50.00)


def test_catalogo_nao_inventa_preco_para_limpeza_ou_sku_comercial(client):
    db = next(app.dependency_overrides[get_db]())
    try:
        categoria = Categoria(nome="Limpeza", tipo="limpeza")
        db.add(categoria)
        db.flush()
        generico = Produto(
            slug="limpador-domestico-teste", nome="Limpador doméstico",
            categoria_id=categoria.id, tipo_produto="generico",
            unidade_consumo="unidade", unidade_venda="frasco",
            venda_fracionada=False, ativo=True,
        )
        comercial = Produto(
            slug="marca-teste-agua-1l", nome="Água Marca Teste",
            categoria_id=categoria.id, tipo_produto="comercial",
            unidade_consumo="unidade", unidade_venda="garrafa",
            venda_fracionada=False, ativo=True,
        )
        db.add_all([generico, comercial])
        db.commit()
    finally:
        db.close()
    lista = client.get("/api/produtos/genericos")
    assert lista.status_code == 200
    slugs = {p["slug"]: p for p in lista.json()}
    assert slugs["limpador-domestico-teste"]["categoria_nome"] == "Limpeza"
    assert slugs["limpador-domestico-teste"]["preco_referencia"] is None
    assert slugs["limpador-domestico-teste"]["preco_referencia_data_base"] is None
    assert "marca-teste-agua-1l" not in slugs
    sku = client.get("/api/produtos?tipo_produto=comercial").json()
    assert next(p for p in sku if p["slug"] == "marca-teste-agua-1l")["preco_referencia"] is None


def test_cobertura_de_referencia_do_motor_planejador_sem_extrapolar_ofertas():
    assert set(CATALOGO_PRODUTOS_PADRAO) == set(PRECOS_REFERENCIA_BRASIL)
    assert REFERENCIA_PRECOS_ATUALIZADA_EM == "2026-09"
    assert all(obter_preco_referencia(slug) > 0 for slug in CATALOGO_PRODUTOS_PADRAO)
    assert obter_preco_referencia("limpador-domestico-teste") is None
