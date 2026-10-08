"""Fase 2D: filiais, importação parcial/idempotente e métricas agregadas."""
from datetime import timedelta

from fastapi.testclient import TestClient

from database.connection import get_db
from main import app
from models import MetricaEstabelecimento
from services.auth import agora
from services.entitlements import LIMITES_PLANOS
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client
from tests.test_tenants_saas import _ativar, _mercado, _sku


def cabecalho(org_id, csrf):
    return {"X-Organizacao-ID": str(org_id), **csrf}


def csv_lote(loja, produto, *, valor="3,49", resto=""):
    return ("estabelecimento_id;produto_id;preco;preco_original;estoque_status\n"
            f"{loja};{produto};{valor};4,50;disponivel\n{resto}")


def test_filiais_codigo_unico_matriz_e_isolamento(client):
    _, h = cadastro_login(client, "filiais-dono@example.com")
    org = _ativar(client, h)
    loja1 = _mercado(client, h, "Filial Principal")
    loja2 = _mercado(client, h, "Filial Bairro")
    url1 = f"/api/parceiro/filiais/{loja1['id']}"
    url2 = f"/api/parceiro/filiais/{loja2['id']}"
    r = client.patch(url1, headers=h, json={"codigo_filial": "CENTRO", "unidade_matriz": True})
    assert r.status_code == 200, r.text
    assert r.json()["unidade_matriz"] is True and r.json()["codigo_filial"] == "CENTRO"
    assert client.patch(url2, headers=h, json={"codigo_filial": "CENTRO"}).status_code == 409
    assert client.patch(url2, headers=h, json={"codigo_filial": "bairro", "unidade_matriz": True}).status_code == 200
    assert client.get("/api/parceiro/filiais").json()[0]["unidade_matriz"] is False
    filiais = client.get("/api/parceiro/filiais").json()
    assert len(filiais) == 2
    assert [f for f in filiais if f["unidade_matriz"]][0]["codigo_filial"] == "BAIRRO"
    assert client.patch(url1, headers=h, json={"ativo": False}).status_code == 200
    assert next(f for f in client.get("/api/parceiro/filiais").json() if f["id"] == loja1["id"])["ativo"] is False

    with TestClient(app) as outro:
        _, h2 = cadastro_login(outro, "filiais-outro@example.com")
        org2 = _ativar(outro, h2)
        assert org2 != org
        assert outro.get("/api/parceiro/filiais", headers={"X-Organizacao-ID": str(org)}).status_code == 404
        assert outro.patch(url1, headers={**h2, "X-Organizacao-ID": str(org2)},
                           json={"codigo_filial": "ATAQUE"}).status_code == 404
        loja_outro = _mercado(outro, h2, "Outra Empresa")
        assert outro.patch(f"/api/parceiro/filiais/{loja_outro['id']}", headers=h2,
                           json={"codigo_filial": "CENTRO"}).status_code == 200
    assert len(client.get("/api/parceiro/filiais").json()) == 2


def test_filiais_so_gestao_e_permissoes(client):
    from tests.test_equipe_organizacao_saas import convite
    _, hd = cadastro_login(client, "filial-permissao-dono@example.com")
    org = _ativar(client, hd)
    loja = _mercado(client, hd, "Filial Gestor")
    with TestClient(app) as editor:
        _, he = cadastro_login(editor, "filial-editor@example.com")
        conv = convite(client, hd, "filial-editor@example.com", "editor")
        assert conv.status_code == 201
        assert editor.post("/api/parceiro/convites/aceitar", headers=he,
                           json={"token": conv.json()["dev_token"]}).status_code == 200
        assert editor.get("/api/parceiro/filiais").status_code == 200
        assert editor.patch(f"/api/parceiro/filiais/{loja['id']}", headers=he,
                            json={"codigo_filial": "X"}).status_code == 403
        assert editor.patch(f"/api/parceiro/filiais/{loja['id']}", json={"codigo_filial": "X"}).status_code == 403
    assert client.patch(f"/api/parceiro/filiais/{loja['id']}", headers=hd,
                        json={"codigo_filial": "x/y"}).status_code == 422


def test_importacao_csv_parcial_repeticao_e_quota(client, monkeypatch):
    _, h = cadastro_login(client, "importador@example.com")
    org = _ativar(client, h)
    loja = _mercado(client, h, "Loja Importadora")
    p = _sku(client, h, "Água Importada 1L", "Marca Importa")
    texto = csv_lote(loja["id"], p["id"], resto=f"99999;{p['id']};2,99;;baixo\n")
    url = "/api/parceiro/importacoes/ofertas"
    payload = {"chave_idempotencia": "importacao-teste-2026", "csv_texto": texto}
    assert client.post(url, json=payload).status_code == 403
    r = client.post(url, headers=h, json=payload)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["criadas"] == 1 and j["rejeitadas"] == 1 and j["linhas"] == 2
    assert j["erros"][0]["linha"] == 3
    resumo = client.get("/api/parceiro/entitlements").json()
    assert resumo["uso"]["ofertas"] == 1
    rep = client.post(url, headers=h, json=payload)
    assert rep.status_code == 201 and rep.json()["repetida"] is True
    assert client.get("/api/parceiro/entitlements").json()["uso"]["ofertas"] == 1
    diferente = {**payload, "csv_texto": texto.replace("3,49", "3,99")}
    assert client.post(url, headers=h, json=diferente).status_code == 409

    monkeypatch.setitem(LIMITES_PLANOS["free"], "ofertas", 1)
    lote2 = client.post(url, headers=h, json={
        "chave_idempotencia": "segunda-importacao-2026",
        "csv_texto": csv_lote(loja["id"], p["id"]),
    })
    assert lote2.status_code == 201, lote2.text
    assert lote2.json()["criadas"] == 0
    assert lote2.json()["rejeitadas"] == 1
    assert client.get("/api/parceiro/entitlements").json()["uso"]["ofertas"] == 1


def test_csv_produto_de_outra_org_e_entrada_invalida(client):
    _, ha = cadastro_login(client, "csv-org-a@example.com")
    org_a = _ativar(client, ha)
    loja_a = _mercado(client, ha, "CSV A")
    produto_a = _sku(client, ha, "Água CSV A", "Marca CSV A")
    with TestClient(app) as b:
        _, hb = cadastro_login(b, "csv-org-b@example.com")
        org_b = _ativar(b, hb)
        loja_b = _mercado(b, hb, "CSV B")
        produto_b = _sku(b, hb, "Água CSV B", "Marca CSV B")
        assert b.post("/api/parceiro/importacoes/ofertas",
                      headers={**hb, "X-Organizacao-ID": str(org_a)},
                      json={"chave_idempotencia": "escopo-tenant-2026",
                            "csv_texto": csv_lote(loja_a["id"], produto_a["id"])}).status_code == 404
        rows = csv_lote(loja_b["id"], produto_a["id"], resto=(
            f"{loja_a['id']};{produto_b['id']};2,99;;baixo\n"
            f"{loja_b['id']};{produto_b['id']};NaN;;disponivel\n"
            f"{loja_b['id']};{produto_b['id']};3,00;;indisponivel\n"
        ))
        res = b.post("/api/parceiro/importacoes/ofertas", headers=hb, json={
            "chave_idempotencia": "csv-orga-produtor-confidencial",
            "csv_texto": rows,
        })
        assert res.status_code == 201, res.text
        assert res.json()["criadas"] == 1 and res.json()["rejeitadas"] == 3
        assert b.get("/api/parceiro/entitlements").json()["uso"]["ofertas"] == 1
    assert client.get("/api/parceiro/entitlements").json()["uso"]["ofertas"] == 0

    invalid = client.post("/api/parceiro/importacoes/ofertas", headers=ha, json={
        "chave_idempotencia": "invalido-cabecalho",
        "csv_texto": "nome;valor\nproduto;12",
    })
    assert invalid.status_code == 422


def test_onboarding_e_relatorio_nao_inventam_receita(client):
    _, h = cadastro_login(client, "relatorio-b2b@example.com")
    org = _ativar(client, h)
    inicial = client.get("/api/parceiro/onboarding").json()
    assert inicial["concluidos"] == 0 and inicial["total"] == 4
    loja = _mercado(client, h, "Loja Relatório")
    sku = _sku(client, h, "Água Relatório", "Marca Relatório")
    assert client.post("/api/parceiro/precos", headers=h, json={
        "estabelecimento_id": loja["id"], "produto_id": sku["id"], "preco": 4.90,
    }).status_code == 201
    db = next(app.dependency_overrides[get_db]())
    try:
        db.add_all([
            MetricaEstabelecimento(estabelecimento_id=loja["id"], tipo="visualizacao"),
            MetricaEstabelecimento(estabelecimento_id=loja["id"], tipo="clique"),
        ])
        db.commit()
    finally:
        db.close()
    onboard = client.get("/api/parceiro/onboarding").json()
    assert onboard["concluidos"] == 3 and onboard["total"] == 4
    assert onboard["passos"][1]["concluido"] is False
    rel = client.get("/api/parceiro/relatorios/comercial?periodo_dias=30")
    assert rel.status_code == 200, rel.text
    d = rel.json()
    assert d["organizacao_id"] == org
    assert d["vendas_confirmadas"] is None and d["receita_confirmada"] is None
    assert d["totais"]["ofertas_registradas"] == 1
    assert d["totais"]["cliques_em_rota"] == 1
    assert d["totais"]["visualizacoes"] == 1
    assert len(d["unidades"]) == 1
    assert client.get("/api/parceiro/relatorios/comercial?periodo_dias=0").status_code == 422
