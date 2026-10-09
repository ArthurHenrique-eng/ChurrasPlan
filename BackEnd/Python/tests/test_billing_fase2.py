"""Fase 2: regressão financeira B2C/B2B apenas em Stripe Test simulado."""
import time

from config import settings
from database.connection import get_db
from main import app
from models import AssinaturaStripeUsuario, AssinaturaOrganizacao
from tests.test_billing_saas import stripe_fake, signed_webhook
from tests.test_billing_usuario_stripe import stripe_pessoal_fake, postar_webhook
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client
from tests.test_tenants_saas import _ativar


def test_fase2_precos_incorretos_bloqueiam_checkout_antes_da_cobranca(client, stripe_pessoal_fake, monkeypatch):
    cadastro_login(client, "precos-premium-fase2@example.com")
    headers = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    # A Stripe retorna 990 no mock; produto comercial esperado não coincide.
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_PREMIUM_MONTHLY_CENTS", 1190)
    r = client.get("/api/billing/usuario/catalogo")
    assert r.status_code == 503 and "divergente" in r.text
    checkout = client.post("/api/billing/usuario/checkout", headers=headers, json={
        "plano": "premium", "periodicidade": "mensal",
        "chave_idempotencia": "preco-divergente-fase2",
    })
    assert checkout.status_code == 503
    assert not any(method == "POST" and path == "/v1/checkout/sessions"
                   for method, path, _, _ in stripe_pessoal_fake["calls"])
    # Mesmo preço ID não pode ser simultaneamente pessoal e empresarial.
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_PREMIUM_MONTHLY_CENTS", 990)
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", settings.STRIPE_PRICE_USER_PREMIUM_MONTHLY)
    assert client.get("/api/billing/usuario/catalogo").status_code == 503


def test_fase2_precos_empresariais_e_live_bloqueados(client, stripe_fake, monkeypatch):
    cadastro_login(client, "precos-empresa-fase2@example.com")
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_BUSINESS_MONTHLY_CENTS", 19990)
    assert client.get("/api/billing/planos-publicos").status_code == 503
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_BUSINESS_MONTHLY_CENTS", 9990)
    assert [x["centavos"] for x in client.get("/api/billing/planos-publicos").json()["planos"]] == [4990, 9990]
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_live_bloqueado")
    assert client.get("/api/billing/planos-publicos").json()["checkout_habilitado"] is False


def test_fase2_anual_empresa_somente_com_valor_aprovado(client, stripe_fake, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO_YEARLY", "price_test_pro_year")
    monkeypatch.setattr(settings, "STRIPE_PRICE_BUSINESS_YEARLY", "price_test_business_year")
    # IDs anuais conhecidos, mas sem valores homologados: catálogo mensal continua utilizável.
    base = client.get("/api/billing/planos-publicos")
    assert base.status_code == 200
    assert {x["periodicidade"] for x in base.json()["planos"]} == {"mensal"}

    import services.billing as billing_service
    original = billing_service.stripe_request

    def fake_with_year(method, path, campos=None, *, idempotency=None):
        if method == "GET" and path.endswith("_year"):
            price_id = path.rsplit("/", 1)[-1]
            return {"id": price_id, "currency": "brl", "livemode": False, "active": True,
                    "recurring": {"interval": "year", "interval_count": 1},
                    "unit_amount": 10000 if price_id == "price_test_pro_year" else 19000}
        return original(method, path, campos, idempotency=idempotency)

    monkeypatch.setattr("services.billing.stripe_request", fake_with_year)
    monkeypatch.setattr("routers.billing.stripe_request", fake_with_year)
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_PRO_YEARLY_CENTS", 10000)
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_BUSINESS_YEARLY_CENTS", 19000)
    atualizado = client.get("/api/billing/planos-publicos")
    assert atualizado.status_code == 200, atualizado.text
    assert len(atualizado.json()["planos"]) == 4
    assert [x["centavos"] for x in atualizado.json()["planos"][2:]] == [10000, 19000]
    # Checkout anual nunca pode ser montado para preço aprovado diferente do Stripe.
    monkeypatch.setattr(settings, "STRIPE_EXPECTED_PRO_YEARLY_CENTS", 9999)
    assert client.get("/api/billing/planos-publicos").status_code == 503


def test_fase2_b2c_renovacao_inadimplencia_cancelamento_reativacao_troca_e_faturas(
    client, stripe_pessoal_fake,
):
    cadastro_login(client, "ciclo-pessoal-fase2@example.com")
    h = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    payload = {"plano": "premium", "periodicidade": "mensal",
               "chave_idempotencia": "fase2-pessoal-checkout"}
    checkout = client.post("/api/billing/usuario/checkout", json=payload, headers=h)
    assert checkout.status_code == 201
    request = next(c for c in stripe_pessoal_fake["calls"]
                   if c[0] == "POST" and c[1] == "/v1/checkout/sessions")
    assert "/minha-conta.html?assinatura=retorno" in request[2]["success_url"]
    assert client.post("/api/billing/usuario/cancelar", headers=h).status_code == 404
    sessao = stripe_pessoal_fake["sessions"]["cs_test_premium_1"]
    sessao["status"], sessao["payment_status"] = "complete", "paid"
    sync = client.post("/api/billing/usuario/sincronizar", headers=h)
    assert sync.status_code == 200 and sync.json()["beneficios_ativos"]
    sid = "sub_premium_1"
    sub = stripe_pessoal_fake["subscriptions"][sid]
    assert client.get("/api/billing/usuario/faturas").json() == [
        client.get("/api/billing/usuario/faturas").json()[0]]
    assert client.get("/api/billing/usuario/faturas").json()[0]["id"] == "in_premium_test"

    # Renovação paga deve atualizar período pelo snapshot atual.
    novo_fim = int(time.time()) + 60 * 60 * 24 * 65
    sub["items"]["data"][0]["current_period_end"] = novo_fim
    renovou = postar_webhook(client, "invoice.paid", {"subscription": sid},
                            eid="evt_fase2_b2c_renew")
    assert renovou.status_code == 200
    db = next(app.dependency_overrides[get_db]())
    try:
        u = db.query(AssinaturaStripeUsuario).first()
        assert abs(u.periodo_fim_em.timestamp() - novo_fim) <= 1
    finally:
        db.close()

    sub["status"] = "past_due"
    assert postar_webhook(client, "invoice.payment_failed", {"subscription": sid},
                         eid="evt_fase2_b2c_pastdue").status_code == 200
    assert not client.get("/api/billing/usuario/assinatura").json()["beneficios_ativos"]
    sub["status"] = "unpaid"
    assert postar_webhook(client, "customer.subscription.updated", {"id": sid,
        "metadata": {"tipo_assinatura": "usuario"}}, eid="evt_fase2_b2c_unpaid").status_code == 200
    assert client.get("/api/billing/usuario/assinatura").json()["plano"] == "free"
    sub["status"] = "active"
    assert postar_webhook(client, "invoice.paid", {"subscription": sid},
                         eid="evt_fase2_b2c_recovered").status_code == 200
    assert client.get("/api/billing/usuario/assinatura").json()["beneficios_ativos"]
    assert client.post("/api/billing/usuario/cancelar").status_code == 403
    cancel = client.post("/api/billing/usuario/cancelar", headers=h)
    assert cancel.status_code == 200 and cancel.json()["cancelamento_agendado"]
    assert client.get("/api/billing/usuario/assinatura").json()["beneficios_ativos"]
    assert client.post("/api/billing/usuario/cancelar", headers=h).status_code == 409
    assert client.post("/api/billing/usuario/trocar-periodo", headers=h, json={
        "periodicidade": "anual", "chave_idempotencia": "cancel-block-periodo",
    }).status_code == 409
    reativar = client.post("/api/billing/usuario/reativar", headers=h)
    assert reativar.status_code == 200 and not reativar.json()["cancelamento_agendado"]
    alterou = client.post("/api/billing/usuario/trocar-periodo", headers=h, json={
        "periodicidade": "anual", "chave_idempotencia": "fase2-pessoal-yearly",
    })
    assert alterou.status_code == 200 and alterou.json()["periodicidade"] == "anual"
    assert client.post("/api/billing/usuario/trocar-periodo", headers=h, json={
        "periodicidade": "anual", "chave_idempotencia": "fase2-yearly-repeat",
    }).status_code == 409
    sub["status"] = "canceled"
    assert postar_webhook(client, "customer.subscription.deleted", {"id": sid,
        "metadata": {"tipo_assinatura": "usuario"}}, eid="evt_fase2_b2c_final").status_code == 200
    assert not client.get("/api/billing/usuario/assinatura").json()["beneficios_ativos"]


def test_fase2_b2b_checkout_retorno_pago_e_reativacao_segura(client, stripe_fake):
    _, h = cadastro_login(client, "retorno-b2b-fase2@example.com")
    oid = _ativar(client, h)
    payload = {"plano": "pro", "periodicidade": "mensal",
               "chave_idempotencia": "checkout-mercado-fase2"}
    r = client.post("/api/billing/checkout", headers=h, json=payload)
    assert r.status_code == 201, r.text
    args = next(call for call in stripe_fake["calls"]
                if call[0] == "POST" and call[1] == "/v1/checkout/sessions")[2]
    assert "/minha-conta.html?cobranca=retorno&organizacao_id=" + str(oid) in args["success_url"]
    assert client.post("/api/billing/sincronizar").status_code == 403
    sem_pgto = client.post("/api/billing/sincronizar", headers=h)
    assert sem_pgto.status_code == 200 and not sem_pgto.json()["beneficios_ativos"]
    sessao = stripe_fake["sessions"]["cs_test_session_1"]
    sessao["status"] = "complete"
    assert not client.post("/api/billing/sincronizar", headers=h).json()["beneficios_ativos"]
    sessao["payment_status"] = "paid"
    sessao["client_reference_id"] = str(oid+999)
    assert client.post("/api/billing/sincronizar", headers=h).status_code == 409
    sessao["client_reference_id"] = str(oid)
    confirmado = client.post("/api/billing/sincronizar", headers=h)
    assert confirmado.status_code == 200 and confirmado.json()["beneficios_ativos"]
    assert confirmado.json()["organizacao_id"] == oid
    assert client.post("/api/billing/sincronizar", headers=h).json()["beneficios_ativos"]
    sub = stripe_fake["subs"]["sub_test_1"]
    cancel = client.post("/api/billing/cancelar", headers=h)
    assert cancel.status_code == 200 and cancel.json()["cancelamento_agendado"]
    assert client.post("/api/billing/reativar", headers=h).json()["cancelamento_agendado"] is False
    assert client.post("/api/billing/reativar", headers=h).status_code == 409
    sub["status"] = "past_due"
    assert signed_webhook(client, "invoice.payment_failed", {"subscription": sub["id"]},
                          event_id="evt_fase2_b2b_pastdue").status_code == 200
    assert client.get("/api/billing/assinatura").json()["tolerancia_ate"] is not None
    sub["status"] = "active"
    assert signed_webhook(client, "invoice.paid", {"subscription": sub["id"]},
                          event_id="evt_fase2_b2b_renovacao").status_code == 200
    assert client.get("/api/billing/assinatura").json()["tolerancia_ate"] is None


def test_fase2_terceiros_nao_conciliam_mercado_pelo_id_do_retorno(client, stripe_fake):
    _, h = cadastro_login(client, "dono-retorno-fase2@example.com")
    oid = _ativar(client, h)
    assert client.post("/api/billing/checkout", headers=h, json={
        "plano": "pro", "chave_idempotencia": "tenant-retorno-fase2",
    }).status_code == 201
    from fastapi.testclient import TestClient
    with TestClient(app) as outsider:
        _, other = cadastro_login(outsider, "outsider-retorno-fase2@example.com")
        _ativar(outsider, other)
        resposta = outsider.post("/api/billing/sincronizar",
                                headers={**other, "X-Organizacao-ID": str(oid)})
        assert resposta.status_code == 404
