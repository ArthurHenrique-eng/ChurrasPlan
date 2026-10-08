"""Cobrança B2B no Stripe TEST; webhooks são a única fonte de concessão paga."""
from __future__ import annotations

import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from config import settings
from database.connection import get_db
from models import (AssinaturaOrganizacao, EventoBilling, OrganizacaoMembro,
                    TentativaCheckout, Usuario)
from services.auth import exigir_papeis
from services.billing import (billing_habilitado, exigir_billing, preco_configurado,
    reconciliar_assinatura, resumo_billing, stripe_request, preco_mensal_validado, validar_destino,
    verificar_assinatura_webhook, assinatura_efetiva)
from services.equipe_organizacao import bloquear_organizacao, membro_ativo
from services.organizacoes import selecionar_organizacao

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    plano: Literal["pro", "business"]
    chave_idempotencia: str


def _proprietario(db: Session, usuario: Usuario, org_id: int | None):
    org = selecionar_organizacao(db, usuario, org_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione a organização para faturamento.")
    membro = membro_ativo(db, usuario, org.id)
    if membro.papel != "proprietario":
        raise HTTPException(status_code=403, detail="Somente proprietário controla assinaturas.")
    return org


def _assinatura(db: Session, org_id: int):
    return db.query(AssinaturaOrganizacao).filter_by(organizacao_id=org_id).first()


@router.get("/catalogo")
def catalogo_stripe_test(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    """Dados monetários vêm exclusivamente de Prices do Stripe Test."""
    _proprietario(db, usuario, organizacao_id)
    exigir_billing()
    return {"sandbox": True, "pagamentos_reais_habilitados": False,
            "planos": [preco_mensal_validado(p) for p in ("pro", "business")]}


@router.get("/assinatura")
def minha_assinatura(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _proprietario(db, usuario, organizacao_id)
    return {**resumo_billing(_assinatura(db, org.id)),
            "organizacao_id": org.id, "checkout_habilitado": billing_habilitado(),
            "pagamentos_reais_habilitados": False}


@router.post("/checkout", status_code=201)
def criar_checkout(
    payload: CheckoutBody,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    exigir_billing()
    chave = payload.chave_idempotencia
    if not (8 <= len(chave) <= 80 and chave[0].isalnum()
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in chave)):
        raise HTTPException(status_code=422, detail="Chave de idempotência inválida.")
    org = _proprietario(db, usuario, organizacao_id)
    bloquear_organizacao(db, org.id)
    tentativa = db.query(TentativaCheckout).filter_by(
        organizacao_id=org.id, chave_idempotencia=chave).first()
    if tentativa:
        if tentativa.plano_slug != payload.plano:
            raise HTTPException(status_code=409, detail="Chave já usada com outro plano.")
        sessao = stripe_request("GET", "/v1/checkout/sessions/" + quote(tentativa.stripe_session_id))
        if sessao.get("id") != tentativa.stripe_session_id or sessao.get("status") != "open":
            raise HTTPException(status_code=409, detail="Checkout anterior encerrado; inicie outro identificador.")
        return {"checkout_url": validar_destino(sessao.get("url", ""), "checkout.stripe.com"),
                "plano": tentativa.plano_slug, "repetida": True}
    atual = _assinatura(db, org.id)
    if assinatura_efetiva(atual) or (atual and atual.status in ("incomplete", "trialing")):
        raise HTTPException(status_code=409, detail="Organização já possui assinatura; utilize gestão da assinatura.")
    preco_mensal_validado(payload.plano)
    campos = {
        "mode": "subscription",
        "line_items[0][price]": preco_configurado(payload.plano),
        "line_items[0][quantity]": "1",
        "customer_email": usuario.email,
        "client_reference_id": str(org.id),
        "metadata[organizacao_id]": str(org.id),
        "metadata[plano_slug]": payload.plano,
        "subscription_data[metadata][organizacao_id]": str(org.id),
        "subscription_data[metadata][plano_slug]": payload.plano,
        "success_url": settings.PUBLIC_APP_URL.rstrip("/") + "/parceiro.html?cobranca=retorno",
        "cancel_url": settings.PUBLIC_APP_URL.rstrip("/") + "/parceiro.html?cobranca=cancelada",
    }
    if atual and atual.stripe_customer_id:
        campos.pop("customer_email")
        campos["customer"] = atual.stripe_customer_id
    sessao = stripe_request("POST", "/v1/checkout/sessions", campos,
                            idempotency=hashlib.sha256(f"churrasplan|{org.id}|{chave}".encode()).hexdigest())
    sid = sessao.get("id")
    if not isinstance(sid, str) or not sid.startswith("cs_test_") or len(sid) > 130:
        raise HTTPException(status_code=502, detail="Sessão Stripe Test inválida.")
    url = validar_destino(sessao.get("url", ""), "checkout.stripe.com")
    db.add(TentativaCheckout(organizacao_id=org.id, usuario_id=usuario.id,
        chave_idempotencia=chave, plano_slug=payload.plano, stripe_session_id=sid))
    db.commit()
    return {"checkout_url": url, "plano": payload.plano, "repetida": False}


@router.get("/faturas")
def listar_faturas(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    exigir_billing()
    org = _proprietario(db, usuario, organizacao_id)
    atual = _assinatura(db, org.id)
    if not atual or not atual.stripe_customer_id:
        return []
    from urllib.parse import urlencode
    resposta = stripe_request("GET", "/v1/invoices?" + urlencode({
        "customer": atual.stripe_customer_id, "limit": 20,
    }))
    return [{
        "id": i["id"], "status": i.get("status"), "moeda": (i.get("currency") or "").upper(),
        "total_centavos": i.get("total"), "pago_centavos": i.get("amount_paid"),
        "criado_em": i.get("created"),
    } for i in resposta.get("data", [])
        if isinstance(i, dict) and i.get("customer") == atual.stripe_customer_id
        and isinstance(i.get("id"), str) and i["id"].startswith("in_")]


@router.post("/trocar-plano")
def trocar_plano(
    payload: CheckoutBody,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    exigir_billing()
    org = _proprietario(db, usuario, organizacao_id)
    bloquear_organizacao(db, org.id)
    atual = _assinatura(db, org.id)
    if not atual or not atual.stripe_subscription_id or not assinatura_efetiva(atual):
        raise HTTPException(status_code=409, detail="Não há assinatura vigente para alterar.")
    if atual.cancelamento_agendado or atual.plano_slug == payload.plano:
        raise HTTPException(status_code=409, detail="Plano já selecionado ou cancelamento agendado.")
    preco_mensal_validado(payload.plano)
    remoto = stripe_request("GET", "/v1/subscriptions/" + quote(atual.stripe_subscription_id))
    itens = (remoto.get("items") or {}).get("data", [])
    if len(itens) != 1 or not isinstance(itens[0].get("id"), str):
        raise HTTPException(status_code=409, detail="Itens da assinatura inválidos.")
    if itens[0].get("price", {}).get("id") != preco_configurado(atual.plano_slug):
        raise HTTPException(status_code=409, detail="Plano Stripe divergente; sincronize antes de trocar.")
    # Stripe pending_if_incomplete: upgrades só passam a valer após pagamento.
    resposta = stripe_request("POST", "/v1/subscriptions/" + quote(atual.stripe_subscription_id), {
        "items[0][id]": itens[0]["id"],
        "items[0][price]": preco_configurado(payload.plano),
        "payment_behavior": "pending_if_incomplete",
        "proration_behavior": "always_invoice",
    }, idempotency=hashlib.sha256(
        f"churrasplan-change|{org.id}|{payload.chave_idempotencia}|{payload.plano}".encode()).hexdigest())
    if resposta.get("id") != atual.stripe_subscription_id:
        raise HTTPException(status_code=502, detail="Troca não confirmada pelo Stripe Test.")
    reconciliar_assinatura(db, atual.stripe_subscription_id)
    db.commit()
    return {**resumo_billing(atual),
            "mensagem": "Troca solicitada. O tier só muda após confirmação do Stripe Test."}


@router.post("/cancelar")
def cancelar_assinatura(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    exigir_billing()
    org = _proprietario(db, usuario, organizacao_id)
    bloquear_organizacao(db, org.id)
    atual = _assinatura(db, org.id)
    if not atual or not atual.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="Não existe assinatura Stripe para cancelar.")
    resposta = stripe_request("POST", "/v1/subscriptions/" + quote(atual.stripe_subscription_id),
                              {"cancel_at_period_end": "true"},
                              idempotency=f"churrasplan-cancel-{org.id}-{atual.stripe_subscription_id}")
    if resposta.get("id") != atual.stripe_subscription_id:
        raise HTTPException(status_code=502, detail="Confirmação de cancelamento inconsistente.")
    reconciliar_assinatura(db, atual.stripe_subscription_id)
    db.commit()
    return {**resumo_billing(atual), "mensagem": "Cancelamento solicitado ao fim do período."}


@router.post("/sincronizar")
def sincronizar_assinatura(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    exigir_billing()
    org = _proprietario(db, usuario, organizacao_id)
    bloquear_organizacao(db, org.id)
    atual = _assinatura(db, org.id)
    if not atual or not atual.stripe_subscription_id:
        return {**resumo_billing(atual), "mensagem": "Sem assinatura vinculada."}
    reconciliar_assinatura(db, atual.stripe_subscription_id)
    db.commit()
    return resumo_billing(atual)


@router.post("/portal")
def portal_cliente(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    exigir_billing()
    org = _proprietario(db, usuario, organizacao_id)
    atual = _assinatura(db, org.id)
    if not atual or not atual.stripe_customer_id:
        raise HTTPException(status_code=404, detail="Cliente Stripe ainda não vinculado.")
    portal = stripe_request("POST", "/v1/billing_portal/sessions", {
        "customer": atual.stripe_customer_id,
        "return_url": settings.PUBLIC_APP_URL.rstrip("/") + "/parceiro.html",
    })
    return {"portal_url": validar_destino(portal.get("url", ""), "billing.stripe.com")}


@router.post("/webhook")
async def webhook_stripe(request: Request, db: Session = Depends(get_db)):
    """Without CSRF/session: Stripe raw body authenticated by HMAC and 5min timestamp."""
    raw = await request.body()
    evento = verificar_assinatura_webhook(raw, request.headers.get("Stripe-Signature", ""))
    eid = evento["id"]
    anterior = db.get(EventoBilling, eid)
    if anterior:
        return {"status": "duplicado"}
    kind = evento.get("type", "")
    obj = evento["data"]["object"]
    stripe_sub = None
    tentativa = None
    if kind == "checkout.session.completed":
        sid = obj.get("id")
        tentativa = db.query(TentativaCheckout).filter_by(stripe_session_id=sid).first()
        if not tentativa:
            raise HTTPException(status_code=409, detail="Checkout não reconhecido.")
        stripe_sub = obj.get("subscription")
    elif kind.startswith("customer.subscription.") and kind in (
        "customer.subscription.created", "customer.subscription.updated",
        "customer.subscription.deleted", "customer.subscription.paused",
        "customer.subscription.resumed"):
        stripe_sub = obj.get("id")
    elif kind in ("invoice.paid", "invoice.payment_failed", "invoice.marked_uncollectible"):
        stripe_sub = obj.get("subscription")
        if not stripe_sub:
            stripe_sub = (obj.get("parent") or {}).get("subscription_details", {}).get("subscription")
    if isinstance(stripe_sub, dict):
        stripe_sub = stripe_sub.get("id")
    organizacao_id = None
    if stripe_sub:
        atual = reconciliar_assinatura(db, stripe_sub, sessao=tentativa)
        organizacao_id = atual.organizacao_id
    # Check again under the tenant lock: concurrent delivery of the same event
    # must never turn a uniqueness conflict into a 500/retry storm.
    if db.get(EventoBilling, eid):
        db.rollback()
        return {"status": "duplicado"}
    db.add(EventoBilling(event_id=eid, event_type=kind[:100],
        organizacao_id=organizacao_id, resultado="reconciliado" if stripe_sub else "ignorado"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(EventoBilling, eid):
            return {"status": "duplicado"}
        raise
    return {"status": "processado" if stripe_sub else "ignorado"}
