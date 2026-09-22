from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from models import Estabelecimento
from schemas.estabelecimento import EstabelecimentoOut

router = APIRouter(prefix="/api/estabelecimentos", tags=["estabelecimentos"])


@router.get("", response_model=list[EstabelecimentoOut])
def listar_estabelecimentos(apenas_ativos: bool = True, db: Session = Depends(get_db)):
    query = db.query(Estabelecimento)
    if apenas_ativos:
        query = query.filter(Estabelecimento.ativo.is_(True))
    return query.order_by(Estabelecimento.nome.asc()).all()


@router.get("/{estabelecimento_id}", response_model=EstabelecimentoOut)
def obter_estabelecimento(estabelecimento_id: int, db: Session = Depends(get_db)):
    estabelecimento = db.get(Estabelecimento, estabelecimento_id)
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")
    return estabelecimento
