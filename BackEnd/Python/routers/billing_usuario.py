"""Contratação Premium pessoal — somente Stripe Test, nunca produção."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal

from config import settings
from database.connection import get_db
from models import AssinaturaStripeUsuario, TentativaCheckoutUsuario, Usuario
from services.auth import usuario_atual, usuario_atual_com_csrf
from services.billing import stripe_request, validar_destino
from services.billing_usuario import (billing_usuario_habilitado, exigir_billing_usuario,
    validar_preco_usuario, preco_usuario, assinatura_usuario_efetiva, resumo_usuario)

router = APIRouter(prefix="/api/billing/usuario", tags=["billing-usuario"])


class CheckoutPremiumBody(BaseModel):
    plano: Literal["premium"]
    periodicidade: Literal["mensal", "anual"] = "mensal"
    chave_idempotencia: str


@router.get("/catalogo")
def catalogo():
    disponiveis = [p for p in ("mensal", "anual") if billing_usuario_habilitado(p)]
    return {"sandbox": True, "pagamentos_reais_habilitados": False,
            "checkout_habilitado": bool(disponiveis),
            "planos": [validar_preco_usuario(p) for p in disponiveis]}


@router.get("/assinatura")
def assinatura_pessoal(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return resumo_usuario(db.get(AssinaturaStripeUsuario, usuario.id))


@router.post("/checkout", status_code=201)
def checkout_pessoal(
    payload: CheckoutPremiumBody, usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    exigir_billing_usuario(payload.periodicidade)
    chave = payload.chave_idempotencia
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,79}", chave):
        raise HTTPException(status_code=422, detail="Chave de idempotência inválida.")
    # Serializa pedidos simultâneos do mesmo titular (InnoDB).
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    anterior = db.query(TentativaCheckoutUsuario).filter_by(
        usuario_id=usuario.id, chave_idempotencia=chave).first()
    if anterior:
        if anterior.plano_slug != payload.plano or anterior.periodicidade != payload.periodicidade:
            raise HTTPException(status_code=409, detail="Chave já utilizada em outro plano/período.")
        sessao = stripe_request("GET", "/v1/checkout/sessions/" + quote(anterior.stripe_session_id, safe=""))
        if sessao.get("status") != "open" or sessao.get("id") != anterior.stripe_session_id:
            raise HTTPException(status_code=409, detail="Checkout anterior encerrado. Inicie uma nova solicitação.")
        return {"checkout_url": validar_destino(sessao.get("url", ""), "checkout.stripe.com"),
                "repetida": True, "sandbox": True}
    atual = db.get(AssinaturaStripeUsuario, usuario.id)
    if assinatura_usuario_efetiva(atual) or (atual and atual.status in ("trialing", "incomplete", "past_due")):
        raise HTTPException(status_code=409, detail="Já existe assinatura pessoal. Gerencie-a no portal.")
    validar_preco_usuario(payload.periodicidade)
    campos = {
        "mode": "subscription",
        "line_items[0][price]": preco_usuario(payload.periodicidade),
        "line_items[0][quantity]": "1",
        "client_reference_id": str(usuario.id),
        "metadata[tipo_assinatura]": "usuario",
        "metadata[usuario_id]": str(usuario.id),
        "subscription_data[metadata][tipo_assinatura]": "usuario",
        "subscription_data[metadata][usuario_id]": str(usuario.id),
        "success_url": settings.PUBLIC_APP_URL.rstrip("/") + "/minha-conta.html?assinatura=retorno",
        "cancel_url": settings.PUBLIC_APP_URL.rstrip("/") + "/planos.html?assinatura=cancelada",
    }
    if atual and atual.stripe_customer_id:
        campos["customer"] = atual.stripe_customer_id
    else:
        campos["customer_email"] = usuario.email
    sessao = stripe_request("POST", "/v1/checkout/sessions", campos,
        idempotency=hashlib.sha256(f"churrasplan-user|{usuario.id}|{chave}".encode()).hexdigest())
    sid = sessao.get("id")
    if not isinstance(sid, str) or not sid.startswith("cs_test_") or len(sid) > 130:
        raise HTTPException(status_code=502, detail="Stripe Test devolveu sessão inválida.")
    url = validar_destino(sessao.get("url", ""), "checkout.stripe.com")
    db.add(TentativaCheckoutUsuario(usuario_id=usuario.id, chave_idempotencia=chave,
        plano_slug=payload.plano, periodicidade=payload.periodicidade, stripe_session_id=sid))
    db.commit()
    return {"checkout_url": url, "repetida": False, "sandbox": True}


@router.post("/sincronizar")
def sincronizar_premium(
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    """Recupera Checkout concluído no Stripe Test caso o webhook tenha atrasado.

    Nunca ativa Premium apenas pelo redirect: exige sessão existente criada
    localmente, titularidade, pagamento confirmado e assinatura Stripe válida.
    """
    from services.billing_usuario import reconciliar_usuario

    atual = db.get(AssinaturaStripeUsuario, usuario.id)
    if assinatura_usuario_efetiva(atual):
        return {**resumo_usuario(atual), "sincronizado": True}

    tentativas = (db.query(TentativaCheckoutUsuario)
                  .filter_by(usuario_id=usuario.id, plano_slug="premium")
                  .order_by(TentativaCheckoutUsuario.id.desc())
                  .limit(10).all())
    for tentativa in tentativas:
        sessao = stripe_request(
            "GET", "/v1/checkout/sessions/" + quote(tentativa.stripe_session_id, safe="")
        )
        if sessao.get("id") != tentativa.stripe_session_id:
            raise HTTPException(status_code=409, detail="Checkout Stripe divergente.")
        if sessao.get("status") != "complete":
            continue
        if (sessao.get("client_reference_id") != str(usuario.id)
                or (sessao.get("metadata") or {}).get("tipo_assinatura") != "usuario"
                or (sessao.get("metadata") or {}).get("usuario_id") != str(usuario.id)):
            raise HTTPException(status_code=409, detail="Titular do Checkout divergente.")
        if sessao.get("payment_status") != "paid":
            continue
        sid = sessao.get("subscription")
        if isinstance(sid, dict):
            sid = sid.get("id")
        if not isinstance(sid, str) or not sid.startswith("sub_"):
            continue
        row = reconciliar_usuario(db, sid, tentativa=tentativa)
        db.commit()
        return {**resumo_usuario(row), "sincronizado": True}

    return {**resumo_usuario(atual), "sincronizado": False}


@router.post("/portal")
def portal_pessoal(usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    if not billing_usuario_habilitado():
        raise HTTPException(status_code=503, detail="Stripe Test não configurado.")
    atual = db.get(AssinaturaStripeUsuario, usuario.id)
    if not atual or not atual.stripe_customer_id:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura pessoal vinculada.")
    sessao = stripe_request("POST", "/v1/billing_portal/sessions", {
        "customer": atual.stripe_customer_id,
        "return_url": settings.PUBLIC_APP_URL.rstrip("/") + "/minha-conta.html",
    })
    return {"portal_url": validar_destino(sessao.get("url", ""), "billing.stripe.com")}
