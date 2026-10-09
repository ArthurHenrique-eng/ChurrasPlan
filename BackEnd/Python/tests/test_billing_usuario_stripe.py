"""Assinatura pessoal Premium com Stripe TEST fake: nenhuma requisição real."""
import hashlib
import hmac
import json
import time

import pytest

from config import settings
from database.connection import get_db
from main import app
from models import AssinaturaStripeUsuario, TentativaCheckoutUsuario
from tests.test_integracao_churrascos import client
from tests.test_fases_3_a_6 import cadastro_login


@pytest.fixture
def stripe_pessoal_fake(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake_user_subscription")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_b2c")
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "")
    monkeypatch.setattr(settings, "STRIPE_PRICE_BUSINESS", "")
    monkeypatch.setattr(settings, "STRIPE_PRICE_USER_PREMIUM_MONTHLY", "price_test_premium_month")
    monkeypatch.setattr(settings, "STRIPE_PRICE_USER_PREMIUM_YEARLY", "price_test_premium_year")
    state = {"sessions": {}, "subscriptions": {}, "calls": []}

    def gateway(method, path, campos=None, *, idempotency=None):
        state["calls"].append((method, path, campos, idempotency))
        if path.startswith("/v1/prices/"):
            yearly = path.endswith("_year")
            return {"id": path.split("/")[-1], "currency": "brl", "active": True,
                    "recurring": {"interval": "year" if yearly else "month", "interval_count": 1},
                    "unit_amount": 9990 if yearly else 990}
        if method == "POST" and path == "/v1/checkout/sessions":
            index = len(state["sessions"]) + 1
            sid, sub_id = f"cs_test_premium_{index}", f"sub_premium_{index}"
            user_id = campos["subscription_data[metadata][usuario_id]"]
            yearly = campos["line_items[0][price]"].endswith("_year")
            state["sessions"][sid] = {"id": sid, "status": "open",
                "payment_status": "unpaid",
                "client_reference_id": campos["client_reference_id"],
                "metadata": {"tipo_assinatura": "usuario", "usuario_id": user_id},
                "url": f"https://checkout.stripe.com/c/pay/test_premium_{index}", "subscription": sub_id}
            state["subscriptions"][sub_id] = {
                "id": sub_id, "status": "active", "customer": f"cus_premium_{index}",
                "metadata": {"tipo_assinatura": "usuario", "usuario_id": user_id},
                "items": {"data": [{"id": f"si_premium_{index}", "price": {"id": campos["line_items[0][price]"]},
                                   "current_period_end": int(time.time()) + (31536000 if yearly else 2592000)}]},
                "cancel_at_period_end": False,
            }
            return state["sessions"][sid]
        if method == "GET" and path.startswith("/v1/checkout/sessions/"):
            return state["sessions"][path.rsplit("/", 1)[-1]]
        if method == "GET" and path.startswith("/v1/subscriptions/"):
            return state["subscriptions"][path.rsplit("/", 1)[-1]]
        if method == "GET" and path.startswith("/v1/invoices?"):
            from urllib.parse import parse_qs, urlsplit
            customer = parse_qs(urlsplit(path).query).get("customer", [""])[0]
            return {"data": [
                {"id": "in_premium_test", "customer": customer, "currency": "brl",
                 "total": 990, "amount_paid": 990, "status": "paid", "created": int(time.time())},
                {"id": "in_outro_cliente", "customer": "cus_incorreto", "currency": "brl",
                 "total": 9999, "amount_paid": 9999, "status": "paid", "created": int(time.time())},
            ]}
        if method == "POST" and path.startswith("/v1/subscriptions/"):
            sub = state["subscriptions"][path.rsplit("/", 1)[-1]]
            if "cancel_at_period_end" in campos:
                sub["cancel_at_period_end"] = campos["cancel_at_period_end"] == "true"
            if "items[0][price]" in campos:
                sub["items"]["data"][0]["price"]["id"] = campos["items[0][price]"]
            return sub
        if method == "POST" and path == "/v1/billing_portal/sessions":
            return {"url": "https://billing.stripe.com/p/session/test",
                    "customer": campos["customer"]}
        raise AssertionError(f"Stripe fake não conhece {method} {path}")

    monkeypatch.setattr("services.billing_usuario.stripe_request", gateway)
    monkeypatch.setattr("routers.billing_usuario.stripe_request", gateway)
    return state


def postar_webhook(client, kind, obj, eid="evt_premium_teste_1", secret="whsec_test_b2c"):
    body = json.dumps({"id": eid, "type": kind, "data": {"object": obj}}).encode("utf-8")
    ts = int(time.time())
    mac = hmac.new(secret.encode(), str(ts).encode() + b"." + body, hashlib.sha256).hexdigest()
    return client.post("/api/billing/webhook", content=body,
                       headers={"Stripe-Signature": f"t={ts},v1={mac}", "Content-Type": "application/json"})


def test_catalogo_publico_premium_independe_dos_precos_b2b(client, stripe_pessoal_fake):
    resp = client.get("/api/billing/usuario/catalogo")
    assert resp.status_code == 200
    assert resp.json()["checkout_habilitado"] is True
    assert [(i["periodicidade"], i["centavos"]) for i in resp.json()["planos"]] == [
        ("mensal", 990), ("anual", 9990)]
    assert client.get("/api/billing/planos-publicos").json()["planos"] == []


def test_retorno_checkout_premium_reconcilia_apenas_pagamento_confirmado(client, stripe_pessoal_fake):
    cadastro_login(client, "retorno-premium@example.com")
    csrf = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    payload = {"plano": "premium", "periodicidade": "mensal",
               "chave_idempotencia": "checkout-retorno-123"}
    resp = client.post("/api/billing/usuario/checkout", json=payload, headers=csrf)
    assert resp.status_code == 201
    assert client.post("/api/billing/usuario/sincronizar").status_code == 403
    sid = "cs_test_premium_1"
    checkout = stripe_pessoal_fake["sessions"][sid]
    # Redirecionamento ou sessão ainda aberta nunca concedem acesso.
    assert client.post("/api/billing/usuario/sincronizar", headers=csrf).json()["beneficios_ativos"] is False
    checkout["status"] = "complete"
    assert client.post("/api/billing/usuario/sincronizar", headers=csrf).json()["beneficios_ativos"] is False
    checkout["payment_status"] = "paid"
    checkout["client_reference_id"] = "999999"
    assert client.post("/api/billing/usuario/sincronizar", headers=csrf).status_code == 409
    checkout["client_reference_id"] = checkout["metadata"]["usuario_id"]
    retorno = client.post("/api/billing/usuario/sincronizar", headers=csrf)
    assert retorno.status_code == 200, retorno.text
    assert retorno.json()["plano"] == "premium" and retorno.json()["beneficios_ativos"]
    assert client.get("/api/planos/minha-assinatura").json()["plano"] == "premium"
    # Operação idempotente, sem criar segunda assinatura.
    assert client.post("/api/billing/usuario/sincronizar", headers=csrf).json()["beneficios_ativos"]


def test_premium_somente_apos_webhook_assinado_e_portal(client, stripe_pessoal_fake):
    cadastro_login(client, "cliente-premium@example.com")
    payload = {"plano": "premium", "periodicidade": "mensal", "chave_idempotencia": "premium-checkout-0001"}
    assert client.post("/api/billing/usuario/checkout", json=payload).status_code == 403
    csrf = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    res = client.post("/api/billing/usuario/checkout", json=payload, headers=csrf)
    assert res.status_code == 201, res.text
    assert res.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    repeat = client.post("/api/billing/usuario/checkout", json=payload, headers=csrf)
    assert repeat.status_code == 201 and repeat.json()["repetida"]
    assert client.post("/api/billing/usuario/checkout", headers=csrf,
        json={**payload, "periodicidade": "anual"}).status_code == 409
    assert client.get("/api/planos/minha-assinatura").json()["plano"] != "premium"
    sid = "cs_test_premium_1"
    sub_id = stripe_pessoal_fake["sessions"][sid]["subscription"]
    assert postar_webhook(client, "checkout.session.completed",
        {"id": sid, "subscription": sub_id}, eid="evt_premium_ok").status_code == 200
    replay = postar_webhook(client, "checkout.session.completed",
        {"id": sid, "subscription": sub_id}, eid="evt_premium_ok")
    assert replay.status_code == 200 and replay.json()["status"] == "duplicado"
    minha = client.get("/api/planos/minha-assinatura").json()
    assert minha["plano"] == "premium" and minha["beneficios_ativos"]
    portal = client.post("/api/billing/usuario/portal", headers=csrf)
    assert portal.status_code == 200
    assert portal.json()["portal_url"].startswith("https://billing.stripe.com/")
    stripe_pessoal_fake["subscriptions"][sub_id]["status"] = "canceled"
    final = postar_webhook(client, "customer.subscription.deleted", {"id": sub_id,
        "metadata": {"tipo_assinatura": "usuario"}}, eid="evt_premium_canceled")
    assert final.status_code == 200, final.text
    assert client.get("/api/planos/minha-assinatura").json()["plano"] == "free"
    assert client.post("/api/billing/usuario/checkout", json={
        "plano": "premium", "periodicidade": "anual", "chave_idempotencia": "premium-renovar-002"}, headers=csrf).status_code == 201


def test_premium_rejeita_chaves_live_preco_invalido_e_metadata_trocada(client, stripe_pessoal_fake, monkeypatch):
    cadastro_login(client, "cliente-validacao@example.com")
    csrf = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    payload = {"plano": "premium", "periodicidade": "anual", "chave_idempotencia": "premium-validar-123"}
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_live_bloqueado")
    assert client.post("/api/billing/usuario/checkout", headers=csrf, json=payload).status_code == 503
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake_user_subscription")
    assert client.post("/api/billing/usuario/checkout", headers=csrf, json=payload).status_code == 201
    sub = stripe_pessoal_fake["subscriptions"]["sub_premium_1"]
    sub["metadata"]["usuario_id"] = "999999"
    res = postar_webhook(client, "checkout.session.completed",
        {"id": "cs_test_premium_1", "subscription": sub["id"]}, eid="evt_premium_cross_user")
    assert res.status_code in (404, 409)
    assert client.get("/api/planos/minha-assinatura").json()["plano"] != "premium"


def test_webhook_premium_mau_assinado_nao_ativa(client, stripe_pessoal_fake):
    cadastro_login(client, "cliente-mac@example.com")
    csrf = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    assert client.post("/api/billing/usuario/checkout", headers=csrf, json={
        "plano": "premium", "chave_idempotencia": "premium-mac-1234"}).status_code == 201
    webhook = postar_webhook(client, "checkout.session.completed",
        {"id": "cs_test_premium_1", "subscription": "sub_premium_1"},
        eid="evt_premium_assinatura", secret="whsec_errado")
    assert webhook.status_code == 400
    assert client.get("/api/planos/minha-assinatura").json()["plano"] != "premium"


def test_webhook_antes_do_checkout_concluido_nao_concede(client, stripe_pessoal_fake):
    cadastro_login(client, "cliente-order@example.com")
    csrf = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    assert client.post("/api/billing/usuario/checkout", headers=csrf, json={
        "plano": "premium", "chave_idempotencia": "premium-order-567"}).status_code == 201
    sub = stripe_pessoal_fake["subscriptions"]["sub_premium_1"]
    response = postar_webhook(client, "customer.subscription.created", sub, eid="evt_sub_before_checkout")
    assert response.status_code == 200 and response.json()["status"] == "aguardando_checkout"
    assert client.get("/api/planos/minha-assinatura").json()["plano"] != "premium"
    assert postar_webhook(client, "checkout.session.completed",
        {"id": "cs_test_premium_1", "subscription": sub["id"]}, eid="evt_checkout_after").status_code == 200
    assert client.get("/api/planos/minha-assinatura").json()["plano"] == "premium"
