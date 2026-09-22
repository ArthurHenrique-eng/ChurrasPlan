from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from models import AssinaturaUsuario, PlanoAssinatura, Usuario
from services.auth import usuario_atual

router = APIRouter(prefix="/api/planos", tags=["planos"])


@router.get("")
def listar_planos(db: Session = Depends(get_db)):
    planos = db.query(PlanoAssinatura).filter(PlanoAssinatura.ativo.is_(True)).order_by(PlanoAssinatura.preco_mensal).all()
    return [{
        "id": p.id, "slug": p.slug, "nome": p.nome, "publico_alvo": p.publico_alvo,
        "preco_mensal": float(p.preco_mensal), "recursos": p.recursos or {},
    } for p in planos]


@router.get("/minha-assinatura")
def minha_assinatura(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    assinatura = db.query(AssinaturaUsuario).filter(AssinaturaUsuario.usuario_id == usuario.id, AssinaturaUsuario.status == "ativa").first()
    if not assinatura:
        return {"plano": usuario.plano, "status": "sem_assinatura_paga", "pagamentos_habilitados": False}
    return {"plano": assinatura.plano.slug, "status": assinatura.status, "termina_em": assinatura.termina_em, "pagamentos_habilitados": False}
