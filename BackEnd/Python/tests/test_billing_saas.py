"""Fase 3: Stripe TEST fake transport, signed webhooks, replay, RBAC, lifecycle."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from config import settings
from database.connection import get_db
from main import app
from models import AssinaturaOrganizacao, EventoBilling, TentativaCheckout
from services.auth import agora
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client
from tests.test_tenants_saas import _ativar
from tests.test_equipe_organizacao_saas import convite


@pytest.fixture
def stripe_fake(monkeypatch):
    """Stripe HTTP is stubbed; keys mimic TEST only; no live network requests."""
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_unit_never_use")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_unit_test")
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_test_pro")
    monkeypatch.setattr(settings, "STRIPE_PRICE_BUSINESS", "price_test_business")
    monkeypatch.setattr(settings, "BILLING_GRACE_DAYS", 3)
    state = {"sessions": {}, "subs": {}, "calls": []}
    def gateway(method, path, campos=None, *, idempotency=None):
        state["calls"].append((method, path, campos, idempotency))
        if path.startswith("/v1/prices/"):
            price_id = path.removeprefix("/v1/prices/")
            return {"id": price_id, "currency": "brl", "active": True,
                    "recurring": {"interval": "month", "interval_count": 1},
                    "unit_amount": 1990 if price_id.endswith("_pro") else 4990}
        if method == "POST" and path == "/v1/checkout/sessions":
            index = len(state["sessions"]) + 1
            session_id = f"cs_test_session_{index}"
            sub_id = f"sub_test_{index}"
            org_id = int(campos["metadata[organizacao_id]"])
            plano = campos["metadata[plano_slug]"]
            state["sessions"][session_id] = {"id": session_id, "status": "open",
                "url": f"https://checkout.stripe.com/c/pay/session_{index}", "subscription": sub_id}
            state["subs"][sub_id] = {"id": sub_id, "status": "active",
                "metadata": {"organizacao_id": str(org_id), "plano_slug": plano},
                "customer": f"cus_fake_{index}", "cancel_at_period_end": False,
                "items": {"data": [{"id": f"si_fake_{index}",
                    "price": {"id": f"price_test_{plano}"},
                    "current_period_end": int(time.time()) + 3600 * 24 * 30}]}}
            return state["sessions"][session_id]
        if path.startswith("/v1/checkout/sessions/"):
            return state["sessions"][path.rsplit("/", 1)[-1]]
        if method == "GET" and path.startswith("/v1/subscriptions/"):
            return state["subs"][path.rsplit("/", 1)[-1]]
        if method == "GET" and path.startswith("/v1/invoices?"):
            from urllib.parse import parse_qs, urlsplit
            customer = parse_qs(urlsplit(path).query).get("customer", [""])[0]
            return {"data": [{"id": "in_fake_1", "customer": customer, "currency": "brl",
                              "total": 1990, "amount_paid": 1990, "status": "paid", "created": int(time.time())}]}
        if method == "POST" and path.startswith("/v1/subscriptions/"):
            item = state["subs"][path.rsplit("/", 1)[-1]]
            if "cancel_at_period_end" in campos:
                item["cancel_at_period_end"] = campos["cancel_at_period_end"] == "true"
            if "items[0][price]" in campos:
                # Simula a alteração confirmada pelo provedor, não pelo browser.
                item["items"]["data"][0]["price"]["id"] = campos["items[0][price]"]
            return item
        if method == "POST" and path == "/v1/billing_portal/sessions":
            return {"url": "https://billing.stripe.com/p/session/test"}
        raise AssertionError(f"Stripe API não prevista: {method} {path}")
    monkeypatch.setattr("services.billing.stripe_request", gateway)
    monkeypatch.setattr("routers.billing.stripe_request", gateway)
    return state


def signed_webhook(client, kind, obj, *, event_id="evt_testing_1", secret="whsec_unit_test", t=None, tamper=False):
    payload = json.dumps({"id": event_id, "type": kind,
                          "data": {"object": obj}}, separators=(",", ":")).encode()
    ts = int(time.time()) if t is None else t
    signature = hmac.new(secret.encode(), str(ts).encode()+b"."+payload, hashlib.sha256).hexdigest()
    if tamper: signature = "0" * len(signature)
    return client.post("/api/billing/webhook", content=payload,
        headers={"Stripe-Signature": f"t={ts},v1={signature}", "Content-Type": "application/json"})


def test_desativado_nao_concede_assinatura(client):
    _, headers = cadastro_login(client, "billing-desligado@example.com")
    org = _ativar(client, headers)
    assert client.post("/api/billing/checkout", headers=headers,
                       json={"plano": "pro", "chave_idempotencia": "primeiro-checkout"}).status_code == 503
    resumo = client.get("/api/parceiro/entitlements").json()
    assert resumo["plano"] == "free"
    assert resumo["checkout_sandbox_habilitado"] is False
    assert resumo["pagamentos_habilitados"] is False
    assert client.get("/api/billing/assinatura").json()["checkout_habilitado"] is False


def test_checkout_webhook_assinatura_ativa_replay_e_cancelamento(client, stripe_fake):
    _, h = cadastro_login(client, "billing-proprietario@example.com")
    org = _ativar(client, h)
    payload = {"plano": "pro", "chave_idempotencia": "checkout-pro-2026"}
    assert client.post("/api/billing/checkout", json=payload).status_code == 403
    created = client.post("/api/billing/checkout", headers=h, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    assert created.json()["repetida"] is False
    repeated = client.post("/api/billing/checkout", headers=h, json=payload)
    assert repeated.status_code == 201 and repeated.json()["repetida"] is True
    assert client.post("/api/billing/checkout", headers=h,
        json={**payload, "plano": "business"}).status_code == 409
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    subscription_id = stripe_fake["sessions"]["cs_test_session_1"]["subscription"]
    webhook = signed_webhook(client, "checkout.session.completed",
        {"id": "cs_test_session_1", "subscription": subscription_id}, event_id="evt_completed_1")
    assert webhook.status_code == 200, webhook.text
    assert webhook.json()["status"] == "processado"
    assert signed_webhook(client, "checkout.session.completed",
        {"id": "cs_test_session_1", "subscription": subscription_id},
        event_id="evt_completed_1").json()["status"] == "duplicado"
    ent = client.get("/api/parceiro/entitlements").json()
    assert ent["plano"] == "pro" and ent["fonte"] == "stripe_test"
    assert ent["pagamentos_habilitados"] is False
    assert ent["billing"]["status"] == "active"
    assert client.get("/api/billing/assinatura").json()["beneficios_ativos"] is True
    assert client.get("/api/billing/catalogo").json()["planos"][0]["centavos"] == 1990
    assert client.post("/api/billing/checkout", headers=h,
                       json={"plano": "business", "chave_idempotencia": "outro-checkout"}).status_code == 409
    portal = client.post("/api/billing/portal", headers=h)
    assert portal.status_code == 200 and portal.json()["portal_url"].startswith("https://billing.stripe.com/")
    canceled = client.post("/api/billing/cancelar", headers=h)
    assert canceled.status_code == 200 and canceled.json()["cancelamento_agendado"] is True
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "pro"
    stripe_fake["subs"][subscription_id]["status"] = "canceled"
    assert signed_webhook(client, "customer.subscription.deleted",
        {"id": subscription_id}, event_id="evt_deleted_1").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    assert client.get("/api/billing/assinatura").json()["beneficios_ativos"] is False
    assert signed_webhook(client, "customer.subscription.created",
        {"id": subscription_id}, event_id="evt_stale_1").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(EventoBilling).filter_by(organizacao_id=org).count() == 3
        assert db.query(TentativaCheckout).filter_by(organizacao_id=org).count() == 1
    finally: db.close()


def test_webhook_assinatura_alterada_ou_fora_da_janela_e_invalida(client, stripe_fake):
    _, h = cadastro_login(client, "billing-assinaturas@example.com")
    org = _ativar(client, h)
    r = client.post("/api/billing/checkout", headers=h,
                    json={"plano": "business", "chave_idempotencia": "bus-2026-uuid"})
    assert r.status_code == 201
    sid = "sub_test_1"
    assert signed_webhook(client, "customer.subscription.updated", {"id": sid},
                          event_id="evt_invalid_sig", tamper=True).status_code == 400
    assert signed_webhook(client, "customer.subscription.updated", {"id": sid},
                          event_id="evt_expired", t=int(time.time())-601).status_code == 400
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    stripe_fake["subs"][sid]["metadata"]["organizacao_id"] = str(org+999)
    assert signed_webhook(client, "customer.subscription.updated", {"id": sid},
                          event_id="evt_cross_org").status_code in (404, 409)
    stripe_fake["subs"][sid]["metadata"]["organizacao_id"] = str(org)
    stripe_fake["subs"][sid]["items"]["data"][0]["price"]["id"] = "price_other"
    assert signed_webhook(client, "customer.subscription.updated", {"id": sid},
                          event_id="evt_wrong_price").status_code == 409
    stripe_fake["subs"][sid]["items"]["data"][0]["price"]["id"] = "price_test_business"
    assert signed_webhook(client, "customer.subscription.created", {"id": sid},
                          event_id="evt_valid").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "business"
    stripe_fake["subs"][sid]["status"] = "past_due"
    assert signed_webhook(client, "invoice.payment_failed", {"subscription": sid},
                          event_id="evt_failed").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "business"
    db = next(app.dependency_overrides[get_db]())
    try:
        row = db.get(AssinaturaOrganizacao, org)
        grace = row.tolerancia_ate
        assert grace is not None
        row.tolerancia_ate = agora() - timedelta(seconds=1)
        db.commit()
    finally: db.close()
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    assert signed_webhook(client, "invoice.payment_failed", {"subscription": sid},
                          event_id="evt_failed_again").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
    stripe_fake["subs"][sid]["status"] = "active"
    assert signed_webhook(client, "invoice.paid", {"subscription": sid},
                          event_id="evt_paid").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "business"


def test_sem_membership_nao_pode_gerir_cobranca(client, stripe_fake):
    _, h = cadastro_login(client, "billing-dono-role@example.com")
    org = _ativar(client, h)
    with TestClient(app) as leitor:
        _, hl = cadastro_login(leitor, "billing-gestor-role@example.com")
        c = convite(client, h, "billing-gestor-role@example.com", "gestor")
        assert leitor.post("/api/parceiro/convites/aceitar", headers=hl,
                           json={"token": c.json()["dev_token"]}).status_code == 200
        assert leitor.get("/api/billing/assinatura").status_code == 403
        assert leitor.post("/api/billing/checkout", headers=hl,
                           json={"plano": "pro", "chave_idempotencia": "gestor-tentando"}).status_code == 403
        assert leitor.post("/api/billing/cancelar", headers=hl).status_code == 403
    with TestClient(app) as outro:
        _, ho = cadastro_login(outro, "billing-outra-org@example.com")
        outra_org = _ativar(outro, ho)
        assert outra_org != org
        assert outro.get("/api/billing/assinatura",
                          headers={"X-Organizacao-ID": str(org)}).status_code == 404
        assert outro.post("/api/billing/checkout", headers={**ho, "X-Organizacao-ID": str(org)},
                          json={"plano": "pro", "chave_idempotencia": "tenant-errado"}).status_code == 404


def test_fatura_e_troca_de_planos_dependem_da_confirmacao_stripe(client, stripe_fake):
    _, h = cadastro_login(client, "billing-upgrade-owner@example.com")
    org = _ativar(client, h)
    assert client.get("/api/billing/catalogo").status_code == 200
    r = client.post("/api/billing/checkout", headers=h,
        json={"plano": "pro", "chave_idempotencia": "upgrade-primeira-compra"})
    assert r.status_code == 201
    assert signed_webhook(client, "checkout.session.completed",
        {"id": "cs_test_session_1", "subscription": "sub_test_1"},
        event_id="evt_checkout_upgrade").status_code == 200
    assert client.get("/api/billing/faturas").json()[0]["status"] == "paid"
    sem_csrf = client.post("/api/billing/trocar-plano",
        json={"plano": "business", "chave_idempotencia": "upgrade-sem-csrf"})
    assert sem_csrf.status_code == 403
    pedido = client.post("/api/billing/trocar-plano", headers=h,
        json={"plano": "business", "chave_idempotencia": "upgrade-2026-teste"})
    assert pedido.status_code == 200, pedido.text
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "business"
    assert client.post("/api/billing/trocar-plano", headers=h,
        json={"plano": "business", "chave_idempotencia": "upgrade-repetido"}).status_code == 409
    assert signed_webhook(client, "customer.subscription.updated",
        {"id": "sub_test_1"}, event_id="evt_novo_plano").status_code == 200
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "business"
    assert client.get("/api/billing/faturas").json()[0]["total_centavos"] == 1990
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.get(AssinaturaOrganizacao, org).plano_slug == "business"
    finally: db.close()


def test_webhook_sem_vinculo_checkout_nunca_concede_tier(client, stripe_fake):
    _, h = cadastro_login(client, "billing-sem-checkout@example.com")
    org = _ativar(client, h)
    stripe_fake["subs"]["sub_forged"] = {"id": "sub_forged", "status": "active",
        "metadata": {"organizacao_id": str(org), "plano_slug": "pro"},
        "customer": "cus_fake_unlinked", "cancel_at_period_end": False,
        "items": {"data": [{"id": "si_unlinked",
                           "price": {"id": "price_test_pro"},
                           "current_period_end": int(time.time())+86400}]}}
    res = signed_webhook(client, "customer.subscription.created", {"id": "sub_forged"},
                         event_id="evt_unlinked_fake")
    assert res.status_code == 409
    assert client.get("/api/parceiro/entitlements").json()["plano"] == "free"
