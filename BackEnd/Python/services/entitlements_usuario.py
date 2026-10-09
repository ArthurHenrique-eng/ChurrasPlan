"""Permissões B2C. Nunca confia em usuarios.plano nem em dados do navegador.

O Stripe Test reconciliado no banco é a única origem de direitos Premium.
Os limites Free atuam somente em novas inclusões; registros existentes
continuam legíveis, editáveis e removíveis depois de um downgrade.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AssinaturaStripeUsuario, Churrasco, Usuario
from services.billing_usuario import assinatura_usuario_efetiva

LIMITE_FREE_PLANEJAMENTOS = 5
RECURSOS_PREMIUM = frozenset({
    "comparacao_avancada", "exportacao_planejamento",
    "modelos_eventos", "analise_detalhada_custos",
})


def premium_usuario(db: Session, usuario_id: int) -> bool:
    assinatura = db.get(AssinaturaStripeUsuario, usuario_id)
    return assinatura_usuario_efetiva(assinatura)


def exigir_premium_usuario(db: Session, usuario: Usuario, recurso: str) -> None:
    if recurso not in RECURSOS_PREMIUM:
        raise ValueError("Recurso individual desconhecido.")
    if not premium_usuario(db, usuario.id):
        raise HTTPException(status_code=403, detail={
            "codigo": "PREMIUM_NECESSARIO",
            "recurso": recurso,
            "mensagem": "Este recurso requer assinatura Premium pessoal ativa.",
        })


def total_planejamentos(db: Session, usuario_id: int) -> int:
    return int(db.execute(
        select(func.count(Churrasco.id)).where(Churrasco.usuario_id == usuario_id)
    ).scalar_one())


def exigir_vaga_planejamento(db: Session, usuario: Usuario) -> None:
    """Chamar na mesma transação da inserção, com lock do usuário até commit."""
    dono = db.query(Usuario).filter_by(id=usuario.id, ativo=True).with_for_update().first()
    if not dono:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    if premium_usuario(db, usuario.id):
        return
    uso = total_planejamentos(db, usuario.id)
    if uso >= LIMITE_FREE_PLANEJAMENTOS:
        raise HTTPException(status_code=409, detail={
            "codigo": "LIMITE_PLANEJAMENTOS_FREE",
            "uso": uso, "limite": LIMITE_FREE_PLANEJAMENTOS,
            "mensagem": "O plano Gratuito permite até cinco planejamentos salvos.",
        })


def resumo_beneficios_usuario(db: Session, usuario: Usuario) -> dict:
    premium = premium_usuario(db, usuario.id)
    uso = total_planejamentos(db, usuario.id)
    return {
        "plano": "premium" if premium else "free",
        "beneficios_ativos": premium,
        "planejamentos": {
            "uso": uso,
            "limite": None if premium else LIMITE_FREE_PLANEJAMENTOS,
            "ilimitado": premium,
            "pode_criar": premium or uso < LIMITE_FREE_PLANEJAMENTOS,
        },
        "recursos": {nome: premium for nome in sorted(RECURSOS_PREMIUM)},
        "sandbox": True,
    }
