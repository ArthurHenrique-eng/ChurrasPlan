from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from models import Preco, Produto
from schemas.estabelecimento import PrecoComparacaoItem, ResumoPrecoOut
from services.calculo_precos import listar_ofertas_atuais, obter_resumo_preco, preco_publicavel

router = APIRouter(prefix="/api/precos", tags=["precos"])


def _item(p: Preco) -> PrecoComparacaoItem:
    return PrecoComparacaoItem(
        preco_id=p.id, produto_id=p.produto_id, produto=p.produto.nome,
        estabelecimento_id=p.estabelecimento_id, estabelecimento=p.estabelecimento.nome,
        preco=float(p.preco), preco_original=float(p.preco_original) if p.preco_original is not None else None,
        unidade_venda=p.produto.unidade_venda,
        coletado_em=p.coletado_em.isoformat() if p.coletado_em else "",
        data_atualizacao=p.data_atualizacao.isoformat() if p.data_atualizacao else "",
        inicio_validade=p.inicio_validade.isoformat() if p.inicio_validade else None,
        fim_validade=p.fim_validade.isoformat() if p.fim_validade else None,
        estoque_status=p.estoque_status, fonte=p.fonte, origem=p.origem,
    )


@router.get("", response_model=list[PrecoComparacaoItem])
def listar_precos(produto_id: int | None = None, atuais: bool = False, db: Session = Depends(get_db)):
    if atuais and produto_id is None: raise HTTPException(status_code=422, detail="Informe produto_id para consultar ofertas atuais.")
    if atuais: return [_item(p) for p in sorted(listar_ofertas_atuais(db, produto_id), key=lambda x: float(x.preco))]
    query = db.query(Preco)
    if produto_id is not None: query = query.filter(Preco.produto_id == produto_id)
    registros = query.order_by(Preco.coletado_em.desc(), Preco.id.desc()).all()
    return [_item(p) for p in registros if preco_publicavel(p)]


@router.get("/comparar", response_model=list[PrecoComparacaoItem])
def comparar_precos(produto_id: int, db: Session = Depends(get_db)):
    if not db.get(Produto, produto_id): raise HTTPException(status_code=404, detail="Produto não encontrado")
    return [_item(p) for p in sorted(listar_ofertas_atuais(db, produto_id), key=lambda x: float(x.preco))]


@router.get("/resumo/{produto_id}", response_model=ResumoPrecoOut)
def resumo_preco(produto_id: int, db: Session = Depends(get_db)):
    resumo = obter_resumo_preco(db, produto_id)
    if not resumo: raise HTTPException(status_code=404, detail="Produto não encontrado")
    return ResumoPrecoOut(**resumo.__dict__)
