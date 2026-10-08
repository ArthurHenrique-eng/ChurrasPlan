from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from models import AssinaturaUsuario, PlanoAssinatura, Usuario
from services.auth import usuario_atual
from services.entitlements import LIMITES_PLANOS, RECURSOS_PLANOS
from services.equipe_organizacao import LIMITES_MEMBROS
from services.billing import billing_habilitado
from models import AssinaturaStripeUsuario
from services.billing_usuario import resumo_usuario

router = APIRouter(prefix="/api/planos", tags=["planos"])


@router.get("")
def listar_planos(db: Session = Depends(get_db)):
    planos = db.query(PlanoAssinatura).filter(PlanoAssinatura.ativo.is_(True)).order_by(PlanoAssinatura.preco_mensal).all()
    return [{
        "id": p.id, "slug": p.slug, "nome": p.nome, "publico_alvo": p.publico_alvo,
        "preco_mensal": float(p.preco_mensal), "recursos": p.recursos or {},
    } for p in planos]


@router.get("/parceiros")
def planos_parceiros():
    """Catálogo técnico de tiers: SEM preço inventado, checkout ou acesso pago."""
    nomes = {"free": "Free", "pro": "Pro", "business": "Business"}
    return [
        {
            "slug": slug, "nome": nomes[slug],
            "limites": {**limites, "membros": LIMITES_MEMBROS[slug]}, "recursos": RECURSOS_PLANOS[slug].copy(),
            "preco_mensal": None, "moeda": "BRL",
            "checkout_habilitado": False, "pagamentos_habilitados": False,
            "checkout_sandbox_habilitado": billing_habilitado() and slug != "free",
            "disponibilidade": "cortesia_administrativa" if slug != "free" else "gratuito",
        }
        for slug, limites in LIMITES_PLANOS.items()
    ]


@router.get("/minha-assinatura")
def minha_assinatura(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    stripe_pessoal = db.get(AssinaturaStripeUsuario, usuario.id)
    if stripe_pessoal:
        return resumo_usuario(stripe_pessoal)
    assinatura = db.query(AssinaturaUsuario).filter(AssinaturaUsuario.usuario_id == usuario.id, AssinaturaUsuario.status == "ativa").first()
    if not assinatura:
        return {"plano": usuario.plano, "status": "sem_assinatura_paga", "pagamentos_habilitados": False}
    return {"plano": assinatura.plano.slug, "status": assinatura.status, "termina_em": assinatura.termina_em, "pagamentos_habilitados": False}
