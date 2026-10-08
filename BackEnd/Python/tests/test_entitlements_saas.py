"""Fase 2B: cotas B2B apenas pelo backend; concessões somente via admin."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from database.connection import get_db
from main import app
from models import AuditoriaAdmin, ConcessaoOrganizacao, Usuario
from services.auth import hash_senha
from services.entitlements import LIMITES_PLANOS
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client
from tests.test_tenants_saas import _ativar, _mercado, _sku


def _admin_logado():
    db = next(app.dependency_overrides[get_db]())
    try:
        db.add(Usuario(
            nome="Admin Planos", email="admin-planos@example.com",
            senha_hash=hash_senha("SenhaAdminPlanos123"), papel="admin", ativo=True,
        ))
        db.commit()
    finally:
        db.close()
    admin_client = TestClient(app)
    r = admin_client.post("/api/auth/login", json={
        "email": "admin-planos@example.com", "senha": "SenhaAdminPlanos123",
    })
    assert r.status_code == 200, r.text
    return admin_client, {"X-CSRF-Token": admin_client.cookies.get("churrasplan_csrf")}


def test_tiers_nao_inventam_preco_e_b2c_permanece_gratuito(client):
    tiers = client.get("/api/planos/parceiros")
    assert tiers.status_code == 200
    assert [t["slug"] for t in tiers.json()] == ["free", "pro", "business"]
    assert all(t["preco_mensal"] is None and not t["checkout_habilitado"] for t in tiers.json())
    _, h = cadastro_login(client, "entitlements-free@example.com")
    assert client.get("/api/planos/minha-assinatura").json()["pagamentos_habilitados"] is False
    org = _ativar(client, h)
    out = client.get("/api/parceiro/entitlements").json()
    assert out["organizacao_id"] == org
    assert out["plano"] == "free" and out["fonte"] == "padrao_gratuito"
    assert out["uso"] == {k: 0 for k in LIMITES_PLANOS["free"]}
    assert out["limites"] == LIMITES_PLANOS["free"]
    assert out["pagamentos_habilitados"] is False
    assert out["checkout_habilitado"] is False


def test_limite_estabelecimento_bloqueia_criacao_mas_nao_edicao(client, monkeypatch):
    monkeypatch.setitem(LIMITES_PLANOS["free"], "estabelecimentos", 1)
    _, h = cadastro_login(client, "cota-lojas@example.com")
    _ativar(client, h)
    loja = _mercado(client, h, "Loja A")
    bloqueio = client.post("/api/parceiro/estabelecimentos", headers=h, json={
        "nome": "Loja B", "tipo": "mercado",
    })
    assert bloqueio.status_code == 409, bloqueio.text
    assert bloqueio.json()["detail"]["codigo"] == "LIMITE_PLANO_ATINGIDO"
    assert bloqueio.json()["detail"]["recurso"] == "estabelecimentos"
    assert client.get("/api/parceiro/entitlements").json()["uso"]["estabelecimentos"] == 1
    edit = client.put(f"/api/parceiro/estabelecimentos/{loja['id']}",
                      headers=h, json={"nome": "Loja A Editada", "tipo": "mercado"})
    assert edit.status_code == 200, edit.text
    assert len(client.get("/api/parceiro/estabelecimentos").json()) == 1


def test_limites_sku_e_ofertas_aplicados_na_mutacao(client, monkeypatch):
    monkeypatch.setitem(LIMITES_PLANOS["free"], "produtos_comerciais", 1)
    monkeypatch.setitem(LIMITES_PLANOS["free"], "ofertas", 1)
    _, h = cadastro_login(client, "cota-sku-ofertas@example.com")
    _ativar(client, h)
    loja = _mercado(client, h, "Loja Cotas")
    sku = _sku(client, h, "Água 1L", "Marca Cotas")
    segunda = client.post("/api/parceiro/produtos", headers=h, json={
        "produto_pai_id": sku["produto_pai_id"], "nome": "Água 2L",
        "marca": "Marca Diferente", "unidade_venda": "garrafa",
        "quantidade_embalagem": 2, "unidade_embalagem": "litro",
    })
    assert segunda.status_code == 409, segunda.text
    assert segunda.json()["detail"]["recurso"] == "produtos_comerciais"
    preco = {"estabelecimento_id": loja["id"], "produto_id": sku["id"], "preco": 3.5}
    assert client.post("/api/parceiro/precos", headers=h, json=preco).status_code == 201
    segundo_preco = client.post("/api/parceiro/precos", headers=h, json={
        **preco, "preco": 2.99,
    })
    assert segundo_preco.status_code == 409, segundo_preco.text
    assert segundo_preco.json()["detail"]["recurso"] == "ofertas"
    uso = client.get("/api/parceiro/entitlements").json()["uso"]
    assert uso["produtos_comerciais"] == 1 and uso["ofertas"] == 1


def test_quota_nao_vaza_entre_organizacoes(client, monkeypatch):
    monkeypatch.setitem(LIMITES_PLANOS["free"], "estabelecimentos", 1)
    _, ha = cadastro_login(client, "cota-org-a@example.com")
    org_a = _ativar(client, ha)
    _mercado(client, ha, "Loja da Organização A")
    with TestClient(app) as b:
        _, hb = cadastro_login(b, "cota-org-b@example.com")
        org_b = _ativar(b, hb)
        assert org_a != org_b
        assert b.get("/api/parceiro/entitlements",
                     headers={"X-Organizacao-ID": str(org_a)}).status_code == 404
        assert b.get("/api/parceiro/entitlements").json()["uso"]["estabelecimentos"] == 0
        x = _mercado(b, hb, "Loja da Organização B")
        assert x["organizacao_id"] == org_b
        assert b.get("/api/parceiro/entitlements").json()["uso"]["estabelecimentos"] == 1


def test_concessao_admin_exige_auth_csrf_validades_e_nao_cobra(client, monkeypatch):
    monkeypatch.setitem(LIMITES_PLANOS["free"], "estabelecimentos", 1)
    monkeypatch.setitem(LIMITES_PLANOS["pro"], "estabelecimentos", 3)
    _, h = cadastro_login(client, "concessao-user@example.com")
    org_id = _ativar(client, h)
    _mercado(client, h, "Mercado Free")

    url = f"/api/admin/organizacoes/{org_id}/concessao"
    expiracao = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    payload = {"plano": "pro", "expira_em": expiracao}
    assert client.put(url, headers=h, json=payload).status_code == 403

    admin, ah = _admin_logado()
    with admin:
        assert admin.put(url, json=payload).status_code == 403
        assert admin.put(url, headers=ah, json={"plano": "business"}).status_code == 422
        assert admin.put(url, headers=ah, json={
            "plano": "pro", "expira_em": (datetime.utcnow()+timedelta(days=2)).isoformat()
        }).status_code == 422
        assert admin.put(url, headers=ah, json={
            "plano": "pro", "expira_em": (datetime.now(UTC)+timedelta(days=367)).isoformat()
        }).status_code == 422
        assert admin.put(url, headers=ah, json={"plano": "premium", "expira_em": expiracao}).status_code == 422
        done = admin.put(url, headers=ah, json=payload)
        assert done.status_code == 200, done.text
        assert done.json()["plano"] == "pro"
        assert done.json()["fonte"] == "cortesia_admin"
        assert done.json()["pagamentos_habilitados"] is False

    assert client.get("/api/parceiro/entitlements").json()["plano"] == "pro"
    _mercado(client, h, "Mercado Cortesia")
    assert len(client.get("/api/parceiro/estabelecimentos").json()) == 2
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(AuditoriaAdmin).filter_by(
            entidade="organizacao", acao="concessao_plano_b2b",
        ).count() == 1
        c = db.get(ConcessaoOrganizacao, org_id)
        assert c is not None and c.origem == "cortesia_admin"
        c.expira_em = datetime.now(UTC).replace(tzinfo=None)-timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    # Mesmo com lojas existentes acima da quota, GET/PUT permanece possível.
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    assert client.get("/api/parceiro/entitlements").json()["fonte"] == "concessao_expirada_ou_invalida"
    assert len(client.get("/api/parceiro/estabelecimentos").json()) == 2
    assert client.post("/api/parceiro/estabelecimentos", headers=h,
                       json={"nome": "Nova Loja", "tipo": "mercado"}).status_code == 409

    with admin:
        revoke = admin.put(url, headers=ah, json={"plano": "free"})
        assert revoke.status_code == 200, revoke.text
        assert revoke.json()["plano"] == "free"
        assert revoke.json()["fonte"] == "padrao_gratuito"
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
