"""Fase 4A: catálogo em massa e campanhas aprovadas sem cobrança."""
from datetime import timedelta

from fastapi.testclient import TestClient

from database.connection import get_db
from main import app
from models import CampanhaComercial, ImportacaoCatalogo, Preco, Produto, Estabelecimento
from services.auth import agora
from services.entitlements import LIMITES_PLANOS
from tests.test_entitlements_saas import _admin_logado
from tests.test_equipe_organizacao_saas import convite
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client
from tests.test_tenants_saas import _ativar, _mercado, _sku


def catalogo_csv(pai, *linhas):
    return ("sku;produto_pai_id;nome;marca;unidade_venda;quantidade_embalagem;unidade_embalagem;ean;ativo\n"
            + "".join(f"{sku};{pai};{nome};{marca};garrafa;1,5;litro;{ean};true\n"
                      for sku, nome, marca, ean in linhas))


def lote(chave, csv):
    return {"chave_idempotencia": chave, "csv_texto": csv}


def test_catalogo_criacao_atualizacao_parcial_e_idempotencia(client):
    _, h = cadastro_login(client, "fase4a-catalogo@example.com")
    org = _ativar(client, h)
    pai = next(x for x in client.get("/api/produtos/genericos").json() if x["slug"] == "agua")
    csv = catalogo_csv(pai["id"], ("REF-001", "Água A", "Marca A", ""),
                       ("REF-002", "Água B", "Marca B", ""))
    p = lote("catalogo-primeiro-lote-2026", csv)
    assert client.post("/api/parceiro/importacoes/catalogo", json=p).status_code == 403
    novo = client.post("/api/parceiro/importacoes/catalogo", json=p, headers=h)
    assert novo.status_code == 201, novo.text
    assert novo.json()["criados"] == 2 and novo.json()["atualizados"] == 0
    assert novo.json()["rejeitados"] == 0
    assert client.post("/api/parceiro/importacoes/catalogo", json=p, headers=h).json()["repetida"] is True
    assert client.get("/api/parceiro/entitlements").json()["uso"]["produtos_comerciais"] == 2
    itens = client.get("/api/parceiro/produtos").json()
    assert {x["sku"] for x in itens} == {"REF-001", "REF-002"}
    original = next(x for x in itens if x["sku"] == "REF-001")["id"]

    atualizar = catalogo_csv(pai["id"], ("REF-001", "Água A Atualizada", "Marca Nova", ""),
                             ("REF-003", "Água C", "Marca C", ""),
                             ("REF-003", "Duplicado", "Marca D", ""))
    reenvio = client.post("/api/parceiro/importacoes/catalogo", headers=h,
                          json=lote("catalogo-segundo-lote-2026", atualizar))
    assert reenvio.status_code == 201, reenvio.text
    assert reenvio.json()["criados"] == 1 and reenvio.json()["atualizados"] == 1
    assert reenvio.json()["rejeitados"] == 1 and reenvio.json()["erros"][0]["linha"] == 4
    final = {p["sku"]: p for p in client.get("/api/parceiro/produtos").json()}
    assert final["REF-001"]["id"] == original and final["REF-001"]["nome"] == "Água A Atualizada"
    assert len(final) == 3
    assert client.post("/api/parceiro/importacoes/catalogo", headers=h,
                       json=lote(p["chave_idempotencia"], atualizar)).status_code == 409
    db = next(app.dependency_overrides[get_db]())
    try:
        logs = db.query(ImportacaoCatalogo).filter_by(organizacao_id=org).all()
        assert len(logs) == 2
        assert all(item.csv_texto if hasattr(item, "csv_texto") else True for item in logs)
        assert "Água A" not in str(logs[0].resultado)
    finally: db.close()


def test_catalogo_quota_erro_e_cross_tenant(client, monkeypatch):
    monkeypatch.setitem(LIMITES_PLANOS["free"], "produtos_comerciais", 1)
    _, ha = cadastro_login(client, "fase4a-quota-a@example.com")
    org_a = _ativar(client, ha)
    pai_id = next(p["id"] for p in client.get("/api/produtos/genericos").json() if p["slug"] == "agua")
    with TestClient(app) as outra:
        _, hb = cadastro_login(outra, "fase4a-quota-b@example.com")
        org_b = _ativar(outra, hb)
        sku_b = outra.post("/api/parceiro/importacoes/catalogo", headers=hb,
                          json=lote("fase4a-lote-b-2026", catalogo_csv(
                              pai_id, ("SKU-B", "Produto B", "Marca B", "1234567890123"))))
        assert sku_b.status_code == 201 and sku_b.json()["criados"] == 1
        assert outra.post("/api/parceiro/importacoes/catalogo",
                          headers={**hb, "X-Organizacao-ID": str(org_a)},
                          json=lote("fase4a-ataque-b-2026", catalogo_csv(
                              pai_id, ("SKU-A", "Produto A", "Marca A", "")))).status_code == 404
    csv = catalogo_csv(pai_id,
                       ("SKU-A", "Produto A", "Marca A", ""),
                       ("SKU-EAN", "Produto Ean", "Marca E", "1234567890123"),
                       ("SKU-COTA", "Produto C", "Marca C", ""))
    resp = client.post("/api/parceiro/importacoes/catalogo", headers=ha,
                       json=lote("fase4a-lote-quota-2026", csv))
    assert resp.status_code == 201, resp.text
    assert (resp.json()["criados"], resp.json()["rejeitados"]) == (1, 2)
    assert client.get("/api/parceiro/entitlements").json()["uso"]["produtos_comerciais"] == 1
    inválido = client.post("/api/parceiro/importacoes/catalogo", headers=ha,
                            json=lote("fase4a-lote-errado-2026", "sku;nome\nXX;Produto"))
    assert inválido.status_code == 422
    assert client.get("/api/parceiro/entitlements").json()["pagamentos_habilitados"] is False


def test_editor_importa_mas_nao_gera_campanha(client):
    _, hd = cadastro_login(client, "fase4a-gestao@example.com")
    _ativar(client, hd)
    with TestClient(app) as editor:
        _, he = cadastro_login(editor, "fase4a-editor@example.com")
        c = convite(client, hd, "fase4a-editor@example.com", "editor")
        assert editor.post("/api/parceiro/convites/aceitar", headers=he,
                           json={"token": c.json()["dev_token"]}).status_code == 200
        pai = next(p["id"] for p in editor.get("/api/produtos/genericos").json() if p["slug"] == "agua")
        res = editor.post("/api/parceiro/importacoes/catalogo", headers=he,
                          json=lote("fase4a-editor-csv-2026",
                                    catalogo_csv(pai, ("SKU-EDITOR", "Água Editor", "Marca Editor", ""))))
        assert res.status_code == 201 and res.json()["criados"] == 1
        assert editor.post("/api/parceiro/campanhas", headers=he, json={
            "codigo": "EDITOR", "nome": "Não autorizado", "inicio_em": agora().isoformat(),
            "fim_em": (agora() + timedelta(days=2)).isoformat(), "preco_ids": [1],
        }).status_code == 403


def test_campanha_revisao_aprovacao_publicidade_cancelamento(client):
    _, h = cadastro_login(client, "fase4a-campanha-owner@example.com")
    org = _ativar(client, h)
    loja = _mercado(client, h, "Loja Publicação")
    sku = _sku(client, h, "Água Publicação", "Marca Publ")
    oferta = client.post("/api/parceiro/precos", headers=h, json={
        "estabelecimento_id": loja["id"], "produto_id": sku["id"],
        "preco": 4.29, "preco_original": 5.29,
    })
    assert oferta.status_code == 201, oferta.text
    preco_id = oferta.json()["preco_id"]
    payload = {
        "codigo": "semana-agua", "nome": "Semana da Água",
        "descricao": "Ofertas da loja verificadas pela moderação",
        "inicio_em": (agora() - timedelta(hours=1)).isoformat(),
        "fim_em": (agora() + timedelta(days=2)).isoformat(),
        "preco_ids": [preco_id],
    }
    assert client.post("/api/parceiro/campanhas", json=payload).status_code == 403
    created = client.post("/api/parceiro/campanhas", headers=h, json=payload)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert created.json()["status"] == "rascunho"
    assert created.json()["ativa_agora"] is False
    assert client.get("/api/campanhas/ativas").json() == []
    assert client.post(f"/api/parceiro/campanhas/{cid}/enviar", headers=h).status_code == 200
    assert client.post(f"/api/parceiro/campanhas/{cid}/enviar", headers=h).status_code == 409
    with TestClient(app) as outra:
        _, ho = cadastro_login(outra, "fase4a-campanha-attacker@example.com")
        _ativar(outra, ho)
        assert outra.get("/api/parceiro/campanhas", headers={"X-Organizacao-ID": str(org)}).status_code == 404
        assert outra.post("/api/parceiro/campanhas", headers=ho,
                          json={**payload, "codigo": "roubo"}).status_code == 404

    admin, ha = _admin_logado()
    with admin:
        assert client.post(f"/api/admin/campanhas/{cid}/revisar",
                           json={"aprovar": True}).status_code == 403
        assert admin.get("/api/admin/campanhas/pendentes").status_code == 200
        rejeitar_sem_motivo = admin.post(f"/api/admin/campanhas/{cid}/revisar", headers=ha,
                                        json={"aprovar": False})
        assert rejeitar_sem_motivo.status_code == 422
        antes_verificacao = admin.post(f"/api/admin/campanhas/{cid}/revisar",
                                       headers=ha, json={"aprovar": True})
        assert antes_verificacao.status_code == 409
        db = next(app.dependency_overrides[get_db]())
        try:
            db.get(Estabelecimento, loja["id"]).parceiro_verificado = True
            db.commit()
        finally: db.close()
        aprovado = admin.post(f"/api/admin/campanhas/{cid}/revisar", headers=ha,
                              json={"aprovar": True})
        assert aprovado.status_code == 200, aprovado.text
        assert aprovado.json()["status"] == "aprovada"
        assert admin.post(f"/api/admin/campanhas/{cid}/revisar",
                          headers=ha, json={"aprovar": False, "motivo": "Cancelamento indevido"}).status_code == 409

    publicas = client.get("/api/campanhas/ativas")
    assert publicas.status_code == 200
    assert any(c["id"] == cid and c["itens"][0]["preco_id"] == preco_id for c in publicas.json())
    assert client.get("/api/parceiro/campanhas").json()[0]["ativa_agora"] is True
    cancelado = client.post(f"/api/parceiro/campanhas/{cid}/cancelar", headers=h)
    assert cancelado.status_code == 200 and cancelado.json()["status"] == "cancelada"
    assert client.get("/api/campanhas/ativas").json() == []
    assert client.get("/api/parceiro/entitlements").json()["checkout_habilitado"] is False


def test_campanha_rejeitada_pode_ser_corrigida_e_nao_aceita_preco_alheio(client):
    _, h = cadastro_login(client, "fase4a-rejeitada@example.com")
    org = _ativar(client, h)
    loja = _mercado(client, h, "Loja Rejeitada")
    sku = _sku(client, h, "Água Rejeitada", "Marca R")
    price = client.post("/api/parceiro/precos", headers=h, json={
        "estabelecimento_id": loja["id"], "produto_id": sku["id"], "preco": 3.0,
    }).json()["preco_id"]
    payload = {"codigo": "revisao", "nome": "Campanha Inicial",
               "inicio_em": (agora() + timedelta(hours=1)).isoformat(),
               "fim_em": (agora() + timedelta(days=3)).isoformat(),
               "preco_ids": [price]}
    with TestClient(app) as outra:
        _, h2 = cadastro_login(outra, "fase4a-rejeitada-outra@example.com")
        _ativar(outra, h2)
        loja2 = _mercado(outra, h2, "Loja Estranha")
        sku2 = _sku(outra, h2, "Água Estranha", "Marca Outra")
        p2 = outra.post("/api/parceiro/precos", headers=h2, json={
            "estabelecimento_id": loja2["id"], "produto_id": sku2["id"], "preco": 9.0,
        }).json()["preco_id"]
        invalida = client.post("/api/parceiro/campanhas", headers=h,
                                json={**payload, "codigo": "invalida", "preco_ids": [p2]})
        assert invalida.status_code == 404
    created = client.post("/api/parceiro/campanhas", headers=h, json=payload)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert client.post(f"/api/parceiro/campanhas/{cid}/enviar", headers=h).status_code == 200
    admin, ha = _admin_logado()
    with admin:
        rec = admin.post(f"/api/admin/campanhas/{cid}/revisar", headers=ha,
                         json={"aprovar": False, "motivo": "Conferir texto promocional"})
        assert rec.status_code == 200 and rec.json()["status"] == "rejeitada"
    assert client.get("/api/campanhas/ativas").json() == []
    edit = client.put(f"/api/parceiro/campanhas/{cid}", headers=h,
                      json={**payload, "nome": "Campanha Corrigida"})
    assert edit.status_code == 200, edit.text
    assert edit.json()["status"] == "rascunho" and edit.json()["nome"] == "Campanha Corrigida"
    assert client.post(f"/api/parceiro/campanhas/{cid}/enviar", headers=h).status_code == 200
