"""Stripe TEST para Premium pessoal, independente dos pagamentos B2B."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, UTC

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import settings
from models import AssinaturaStripeUsuario, TentativaCheckoutUsuario, Usuario, EventoBilling
from services.billing import stripe_request, fim_periodo_stripe, VALID_STATUSES, validar_destino
from services.entitlements import agora_utc

PRICE_FIELDS_USUARIO = {
    "mensal": "STRIPE_PRICE_USER_PREMIUM_MONTHLY",
    "anual": "STRIPE_PRICE_USER_PREMIUM_YEARLY",
}


def billing_usuario_habilitado(periodicidade: str | None = None) -> bool:
    if not (settings.BILLING_ENABLED and settings.STRIPE_SECRET_KEY.startswith("sk_test_")
            and settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")):
        return False
    if periodicidade:
        return periodicidade in PRICE_FIELDS_USUARIO and getattr(settings, PRICE_FIELDS_USUARIO[periodicidade], "").startswith("price_")
    return any(getattr(settings, v, "").startswith("price_") for v in PRICE_FIELDS_USUARIO.values())


def exigir_billing_usuario(periodicidade: str) -> None:
    if not billing_usuario_habilitado(periodicidade):
        raise HTTPException(status_code=503, detail="Assinatura Premium Stripe Test não configurada para este período.")


def preco_usuario(periodicidade: str) -> str:
    exigir_billing_usuario(periodicidade)
    return getattr(settings, PRICE_FIELDS_USUARIO[periodicidade])


def validar_preco_usuario(periodicidade: str) -> dict:
    price_id = preco_usuario(periodicidade)
    price = stripe_request("GET", "/v1/prices/" + urllib.parse.quote(price_id, safe=""))
    periodo = "month" if periodicidade == "mensal" else "year"
    recurring = price.get("recurring") or {}
    if (price.get("id") != price_id or price.get("currency") != "brl"
            or recurring.get("interval") != periodo or recurring.get("interval_count", 1) != 1
            or not price.get("active") or not isinstance(price.get("unit_amount"), int)
            or price["unit_amount"] <= 0):
        raise HTTPException(status_code=503, detail="Preço Premium inválido no Stripe Test.")
    return {"plano": "premium", "publico": "usuario", "periodicidade": periodicidade,
            "moeda": "BRL", "centavos": price["unit_amount"]}


def assinatura_usuario_efetiva(row: AssinaturaStripeUsuario | None) -> bool:
    return bool(row and row.plano_slug == "premium" and row.status == "active"
                and row.periodo_fim_em is not None and row.periodo_fim_em > agora_utc())


def resumo_usuario(row: AssinaturaStripeUsuario | None) -> dict:
    return {"plano": "premium" if assinatura_usuario_efetiva(row) else "free",
            "status": row.status if row else "sem_assinatura",
            "periodicidade": row.periodicidade if row else None,
            "periodo_fim_em": row.periodo_fim_em if row else None,
            "cancelamento_agendado": row.cancelamento_agendado if row else False,
            "beneficios_ativos": assinatura_usuario_efetiva(row),
            "checkout_habilitado": billing_usuario_habilitado(),
            "sandbox": True, "pagamentos_reais_habilitados": False}


def reconciliar_usuario(db: Session, sub_id: str, *, tentativa: TentativaCheckoutUsuario | None = None) -> AssinaturaStripeUsuario:
    """Somente Checkout iniciado localmente consegue vincular Premium ao usuário."""
    if not isinstance(sub_id, str) or not sub_id.startswith("sub_") or len(sub_id) > 100:
        raise HTTPException(status_code=422, detail="Assinatura Stripe inválida.")
    sub = stripe_request("GET", "/v1/subscriptions/" + urllib.parse.quote(sub_id, safe=""))
    if sub.get("id") != sub_id or sub.get("status") not in VALID_STATUSES:
        raise HTTPException(status_code=409, detail="Snapshot da assinatura inválido.")
    metadata = sub.get("metadata") or {}
    if metadata.get("tipo_assinatura") != "usuario":
        raise HTTPException(status_code=409, detail="Assinatura não pertence a usuário.")
    try:
        usuario_id = int(metadata.get("usuario_id") or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="Titular inválido.") from exc
    usuario = db.query(Usuario).filter_by(id=usuario_id, ativo=True).with_for_update().first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    itens = (sub.get("items") or {}).get("data") or []
    if len(itens) != 1 or not isinstance(itens[0].get("price"), dict):
        raise HTTPException(status_code=409, detail="Assinatura deve ter um preço.")
    price_id = itens[0]["price"].get("id")
    periodicidade = next((p for p, f in PRICE_FIELDS_USUARIO.items()
                          if getattr(settings, f, "") and price_id == getattr(settings, f)), None)
    if not periodicidade:
        raise HTTPException(status_code=409, detail="Preço de usuário não autorizado.")
    cliente = sub.get("customer")
    if isinstance(cliente, dict):
        cliente = cliente.get("id")
    if not isinstance(cliente, str) or not cliente.startswith("cus_") or len(cliente) > 100:
        raise HTTPException(status_code=409, detail="Cliente Stripe inválido.")
    if tentativa is None:
        tentativa = db.query(TentativaCheckoutUsuario).filter_by(
            usuario_id=usuario_id, stripe_subscription_id=sub_id).first()
    if not tentativa or tentativa.usuario_id != usuario_id:
        raise HTTPException(status_code=409, detail="Checkout local não confirmado.")
    if tentativa.plano_slug != "premium":
        raise HTTPException(status_code=409, detail="Plano local divergente.")
    row = db.get(AssinaturaStripeUsuario, usuario_id)
    if row is None:
        row = AssinaturaStripeUsuario(usuario_id=usuario_id)
        db.add(row)
    elif row.stripe_subscription_id and row.stripe_subscription_id != sub_id:
        if assinatura_usuario_efetiva(row) or row.status not in ("canceled", "incomplete_expired"):
            raise HTTPException(status_code=409, detail="Já existe uma assinatura pessoal.")
    if row.stripe_customer_id and row.stripe_customer_id != cliente:
        raise HTTPException(status_code=409, detail="Cliente da assinatura divergente.")
    fim = fim_periodo_stripe(sub)
    if sub["status"] == "active" and not fim:
        raise HTTPException(status_code=409, detail="Assinatura ativa sem período.")
    row.stripe_customer_id, row.stripe_subscription_id = cliente, sub_id
    row.plano_slug, row.periodicidade, row.status = "premium", periodicidade, sub["status"]
    row.periodo_fim_em, row.cancelamento_agendado = fim, bool(sub.get("cancel_at_period_end"))
    row.sincronizado_em = agora_utc()
    tentativa.stripe_subscription_id = sub_id
    return row


def processar_webhook_usuario(db: Session, evento: dict) -> dict | None:
    """Despacha somente eventos identificados como B2C; outros seguem no handler B2B."""
    eid, kind = evento["id"], evento.get("type", "")
    obj = evento["data"]["object"]
    sid = None
    tentativa = None
    if kind == "checkout.session.completed":
        tentativa = db.query(TentativaCheckoutUsuario).filter_by(stripe_session_id=obj.get("id")).first()
        if tentativa:
            sid = obj.get("subscription")
            if isinstance(sid, dict): sid = sid.get("id")
            if not sid:
                raise HTTPException(status_code=409, detail="Checkout Premium sem assinatura.")
        else:
            return None
    elif kind in ("customer.subscription.created", "customer.subscription.updated",
                  "customer.subscription.deleted", "customer.subscription.paused",
                  "customer.subscription.resumed", "invoice.paid", "invoice.payment_failed",
                  "invoice.marked_uncollectible"):
        if kind.startswith("customer.subscription."):
            sid = obj.get("id")
            # Evento anterior ao checkout concluído: sucesso posterior reconciliará snapshot.
            if (obj.get("metadata") or {}).get("tipo_assinatura") == "usuario":
                tentativa = db.query(TentativaCheckoutUsuario).filter_by(stripe_subscription_id=sid).first()
                if not tentativa:
                    return {"status": "aguardando_checkout"}
        else:
            sid = obj.get("subscription")
            if not sid:
                sid = ((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription")
        if isinstance(sid, dict): sid = sid.get("id")
        if not isinstance(sid, str): return None
        tentativa = db.query(TentativaCheckoutUsuario).filter_by(stripe_subscription_id=sid).first()
        if not tentativa: return None
    else:
        return None

    if db.get(EventoBilling, eid):
        return {"status": "duplicado"}
    row = reconciliar_usuario(db, sid, tentativa=tentativa)
    db.add(EventoBilling(event_id=eid, event_type=kind[:100],
                        organizacao_id=None, resultado="usuario_reconciliado"))
    from sqlalchemy.exc import IntegrityError
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(EventoBilling, eid):
            return {"status": "duplicado"}
        raise
    return {"status": "processado", "publico": "usuario"}
