"""Stripe Billing TEST: provider requests, verification and authoritative entitlements.

Never mint B2B paid rights from user inputs, checkout redirects or invoice-only events.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, UTC
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import settings
from models import AssinaturaOrganizacao, TentativaCheckout, Organizacao
from services.entitlements import agora_utc

VALID_STATUSES = {"active", "trialing", "past_due", "canceled", "unpaid", "incomplete", "incomplete_expired", "paused"}
ELIGIBLE_STATUSES = {"active"}
PRICE_FIELDS = {"pro": "STRIPE_PRICE_PRO", "business": "STRIPE_PRICE_BUSINESS"}
PRICE_FIELDS_YEARLY = {"pro": "STRIPE_PRICE_PRO_YEARLY", "business": "STRIPE_PRICE_BUSINESS_YEARLY"}


def billing_habilitado() -> bool:
    """Only TEST Stripe secret+webhook secret+both recurring price IDs."""
    return bool(settings.BILLING_ENABLED
                and settings.STRIPE_SECRET_KEY.startswith("sk_test_")
                and settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")
                and all(getattr(settings, field).startswith("price_") for field in PRICE_FIELDS.values())
                and 0 <= settings.BILLING_GRACE_DAYS <= 7)


def exigir_billing() -> None:
    if not billing_habilitado():
        raise HTTPException(status_code=503, detail="Stripe Test não configurado. Cobrança real permanece desativada.")


def preco_configurado(plano: str, periodicidade: str = "mensal") -> str:
    if plano not in PRICE_FIELDS or periodicidade not in ("mensal", "anual"):
        raise HTTPException(status_code=422, detail="Plano ou periodicidade B2B inválidos.")
    campo = (PRICE_FIELDS if periodicidade == "mensal" else PRICE_FIELDS_YEARLY)[plano]
    price_id = getattr(settings, campo)
    if not price_id.startswith("price_"):
        raise HTTPException(status_code=503, detail="Preço do período não configurado no Stripe Test.")
    return price_id


def stripe_request(method: str, path: str, campos: dict | None = None, *, idempotency: str | None = None) -> dict:
    # A API é compartilhada por Billing B2B e Premium B2C; não exige ambos os
    # preços de mercados para a contratação pessoal. Sempre recusa modo live.
    if not (settings.BILLING_ENABLED and settings.STRIPE_SECRET_KEY.startswith("sk_test_")
            and settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")):
        raise HTTPException(status_code=503, detail="Stripe Test não configurado.")
    if not path.startswith("/v1/") or "://" in path or ".." in path:
        raise ValueError("Endpoint Stripe inválido")
    body = urllib.parse.urlencode(campos).encode("utf-8") if campos is not None else None
    headers = {"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}", "Content-Type": "application/x-www-form-urlencoded"}
    if idempotency:
        headers["Idempotency-Key"] = idempotency
    req = urllib.request.Request("https://api.stripe.com" + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as resposta:
            return json.loads(resposta.read(250000).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Falha na comunicação com Stripe Test.") from exc


def validar_destino(url: str, dominio: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != dominio or parsed.username or parsed.password:
        raise HTTPException(status_code=502, detail="Endereço de checkout do provedor inválido.")
    return url


def preco_mensal_validado(plano: str, periodicidade: str = "mensal") -> dict:
    """Valida preço recorrente mensal/anual; nunca aceita valor do browser."""
    price_id = preco_configurado(plano, periodicidade)
    dado = stripe_request("GET", "/v1/prices/" + urllib.parse.quote(price_id, safe=""))
    intervalo = (dado.get("recurring") or {}).get("interval")
    campo_esperado = {
        ("pro", "mensal"): "STRIPE_EXPECTED_PRO_MONTHLY_CENTS",
        ("business", "mensal"): "STRIPE_EXPECTED_BUSINESS_MONTHLY_CENTS",
        ("pro", "anual"): "STRIPE_EXPECTED_PRO_YEARLY_CENTS",
        ("business", "anual"): "STRIPE_EXPECTED_BUSINESS_YEARLY_CENTS",
    }[(plano, periodicidade)]
    valor_esperado = getattr(settings, campo_esperado)
    if valor_esperado < 0:
        raise HTTPException(status_code=503, detail="Expectativa comercial de preço inválida.")
    # Rejeita Price IDs compartilhados entre tiers (inclusive usuário pessoal).
    ids = [getattr(settings, campo, "") for campo in [
        "STRIPE_PRICE_PRO", "STRIPE_PRICE_BUSINESS", "STRIPE_PRICE_PRO_YEARLY",
        "STRIPE_PRICE_BUSINESS_YEARLY", "STRIPE_PRICE_USER_PREMIUM_MONTHLY",
        "STRIPE_PRICE_USER_PREMIUM_YEARLY"]]
    ativos = [pid for pid in ids if pid.startswith("price_")]
    if len(ativos) != len(set(ativos)):
        raise HTTPException(status_code=503, detail="Price IDs duplicados entre planos; confira o Stripe Test.")
    if (dado.get("id") != price_id or dado.get("currency") != "brl"
            or intervalo != ("month" if periodicidade == "mensal" else "year") or (dado.get("recurring") or {}).get("interval_count", 1) != 1
            or not isinstance(dado.get("unit_amount"), int)
            or dado["unit_amount"] <= 0 or not dado.get("active")
            or dado.get("livemode") is True):
        raise HTTPException(status_code=503, detail="Preço BRL recorrente do plano inválido no Stripe Test.")
    if valor_esperado and dado["unit_amount"] != valor_esperado:
        raise HTTPException(status_code=503, detail=(
            f"Preço {plano}/{periodicidade} divergente: Stripe Test retorna "
            f"{dado['unit_amount']} centavos, esperado {valor_esperado}. "
            "Corrija o Price ID no .env antes de contratar."
        ))
    return {"plano": plano, "moeda": "BRL", "centavos": dado["unit_amount"],
            "preco_id": price_id, "periodicidade": periodicidade}


def verificar_assinatura_webhook(payload: bytes, assinatura: str) -> dict:
    if not (settings.BILLING_ENABLED and settings.STRIPE_SECRET_KEY.startswith("sk_test_")
            and settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")):
        raise HTTPException(status_code=503, detail="Stripe Test webhook não configurado.")
    if len(payload) > 250000:
        raise HTTPException(status_code=413, detail="Evento acima do limite.")
    partes = {}
    for item in assinatura.split(","):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            partes.setdefault(k, []).append(v)
    try:
        timestamp = int(partes["t"][0])
    except (KeyError, ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail="Assinatura de webhook inválida.") from exc
    if abs(time.time() - timestamp) > 300:
        raise HTTPException(status_code=400, detail="Timestamp de webhook expirado.")
    valor = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(),
                     str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(valor, teste) for teste in partes.get("v1", [])):
        raise HTTPException(status_code=400, detail="Webhook não autenticado.")
    try:
        evento = json.loads(payload)
        if not isinstance(evento, dict) or not isinstance(evento.get("data", {}).get("object"), dict):
            raise ValueError("Evento incompleto")
        if not isinstance(evento.get("id"), str) or not evento["id"].startswith("evt_"):
            raise ValueError("ID inválido")
        return evento
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Evento Stripe inválido.") from exc


def fim_periodo_stripe(obj: dict) -> datetime | None:
    """Stripe Basil removed subscription top-level period; inspect subscription items."""
    periodos = [item.get("current_period_end")
                for item in obj.get("items", {}).get("data", [])
                if isinstance(item, dict) and isinstance(item.get("current_period_end"), int)]
    timestamp = max(periodos, default=obj.get("current_period_end"))
    return datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None) if isinstance(timestamp, int) and timestamp > 0 else None


def reconciliar_assinatura(db: Session, stripe_id: str, *, sessao: TentativaCheckout | None = None) -> AssinaturaOrganizacao:
    """Always retrieve the latest Stripe subscription snapshot: out-of-order events safe."""
    if not stripe_id.startswith("sub_") or len(stripe_id) > 100:
        raise HTTPException(status_code=422, detail="Assinatura Stripe inválida.")
    remoto = stripe_request("GET", "/v1/subscriptions/" + urllib.parse.quote(stripe_id, safe=""))
    if remoto.get("id") != stripe_id:
        raise HTTPException(status_code=502, detail="Assinatura do provedor inconsistente.")
    metadata = remoto.get("metadata") or {}
    try:
        org_id = int(metadata.get("organizacao_id", "0"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=409, detail="Metadata da assinatura não identificada.") from exc
    itens = remoto.get("items", {}).get("data", [])
    if len(itens) != 1 or not isinstance(itens[0].get("price"), dict):
        raise HTTPException(status_code=409, detail="Item de assinatura Stripe inválido.")
    preco_real = itens[0]["price"].get("id")
    # A lista de Price IDs configurados no servidor é a fonte do tier.
    # Evita metadata antiga após troca pelo Customer Portal.
    selecionado = next(((slug, periodo) for periodo, campos in
                       (("mensal", PRICE_FIELDS), ("anual", PRICE_FIELDS_YEARLY))
                       for slug, nome_campo in campos.items()
                       if getattr(settings, nome_campo, "") and preco_real == getattr(settings, nome_campo)), None)
    if selecionado is None or org_id < 1:
        raise HTTPException(status_code=409, detail="Price ID da assinatura não autorizado.")
    plano, periodicidade = selecionado
    cliente = remoto.get("customer")
    if isinstance(cliente, dict):
        cliente = cliente.get("id")
    if not isinstance(cliente, str) or not cliente.startswith("cus_") or len(cliente) > 100:
        raise HTTPException(status_code=409, detail="Cliente Stripe inválido.")
    org = db.query(Organizacao).filter_by(id=org_id, ativo=True).with_for_update().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização Stripe inexistente ou desativada.")
    if sessao and (sessao.organizacao_id != org_id
                   or (sessao.stripe_subscription_id and sessao.stripe_subscription_id != stripe_id)):
        raise HTTPException(status_code=409, detail="Sessão e assinatura não correspondem.")
    # Only a locally-created Checkout attempt can bootstrap the first subscription.
    atual = db.query(AssinaturaOrganizacao).filter_by(organizacao_id=org_id).with_for_update().first()
    if atual is None:
        tentativa = sessao or db.query(TentativaCheckout).filter_by(organizacao_id=org_id, plano_slug=plano).order_by(TentativaCheckout.id.desc()).first()
        if not tentativa:
            raise HTTPException(status_code=409, detail="Assinatura não originada no checkout da plataforma.")
        if tentativa.stripe_subscription_id not in (None, stripe_id):
            raise HTTPException(status_code=409, detail="Referência Stripe divergente.")
        atual = AssinaturaOrganizacao(organizacao_id=org_id)
        db.add(atual)
    elif atual.stripe_subscription_id and atual.stripe_subscription_id != stripe_id:
        # Novo checkout permitido apenas depois de término efetivo da antiga.
        tentativa = sessao or db.query(TentativaCheckout).filter_by(
            organizacao_id=org_id, plano_slug=plano,
            stripe_subscription_id=stripe_id).first()
        if (assinatura_efetiva(atual) or atual.status not in ("canceled", "incomplete_expired")
                or not tentativa):
            raise HTTPException(status_code=409, detail="Outra assinatura já pertence à organização.")
    if atual.stripe_customer_id and atual.stripe_customer_id != cliente:
        raise HTTPException(status_code=409, detail="Customer Stripe divergente.")
    status = remoto.get("status")
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=409, detail="Status Stripe desconhecido.")
    fim = fim_periodo_stripe(remoto)
    if status in ELIGIBLE_STATUSES and not fim:
        raise HTTPException(status_code=409, detail="Assinatura ativa sem término do período.")
    agora = agora_utc()
    if status == "past_due":
        # Grace period only from first failure; replay must not extend it.
        limite = agora + timedelta(days=settings.BILLING_GRACE_DAYS)
        if not atual.tolerancia_ate:
            atual.tolerancia_ate = limite
    else:
        atual.tolerancia_ate = None
    atual.status, atual.plano_slug, atual.periodicidade = status, plano, periodicidade
    atual.stripe_subscription_id, atual.stripe_customer_id = stripe_id, cliente
    atual.periodo_fim_em, atual.cancelamento_agendado = fim, bool(remoto.get("cancel_at_period_end"))
    atual.sincronizado_em = agora
    if sessao:
        sessao.stripe_subscription_id = stripe_id
    return atual


def assinatura_efetiva(assinatura: AssinaturaOrganizacao | None) -> bool:
    if not assinatura or assinatura.plano_slug not in PRICE_FIELDS:
        return False
    agora = agora_utc()
    return bool(
        (assinatura.status == "active" and assinatura.periodo_fim_em is not None
         and assinatura.periodo_fim_em > agora)
        or (assinatura.status == "past_due" and assinatura.tolerancia_ate is not None
            and assinatura.tolerancia_ate > agora and assinatura.periodo_fim_em is not None
            and assinatura.periodo_fim_em + timedelta(days=settings.BILLING_GRACE_DAYS) > agora)
    )


def resumo_billing(assinatura: AssinaturaOrganizacao | None) -> dict:
    return {
        "plano": assinatura.plano_slug if assinatura else "free",
        "periodicidade": assinatura.periodicidade if assinatura else None,
        "status": assinatura.status if assinatura else "sem_assinatura",
        "periodo_fim_em": assinatura.periodo_fim_em if assinatura else None,
        "tolerancia_ate": assinatura.tolerancia_ate if assinatura else None,
        "cancelamento_agendado": assinatura.cancelamento_agendado if assinatura else False,
        "beneficios_ativos": assinatura_efetiva(assinatura),
        "sandbox": True,
    }
