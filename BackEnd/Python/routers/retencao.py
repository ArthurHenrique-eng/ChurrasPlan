from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import get_db
from models import Usuario, Estabelecimento, Churrasco, FavoritoEstabelecimento, LembreteEvento, TarefaOutbox
from services.auth import usuario_atual, usuario_atual_com_csrf, agora
from services.outbox import enfileirar

router = APIRouter(prefix="/api/retencao", tags=["retenção solicitada"])


@router.get("/favoritos")
def favoritos(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return [{"id": e.id, "nome": e.nome} for e in db.query(Estabelecimento).join(FavoritoEstabelecimento,
        FavoritoEstabelecimento.estabelecimento_id == Estabelecimento.id).filter(
        FavoritoEstabelecimento.usuario_id == usuario.id, Estabelecimento.ativo.is_(True), Estabelecimento.parceiro_verificado.is_(True)).all()]


@router.put("/favoritos/{estabelecimento_id}", status_code=204)
def favoritar(estabelecimento_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    e = db.query(Estabelecimento).filter_by(id=estabelecimento_id, ativo=True, parceiro_verificado=True).first()
    if not e:
        raise HTTPException(404, detail="Estabelecimento público não encontrado.")
    if not db.get(FavoritoEstabelecimento, (usuario.id, estabelecimento_id)):
        db.add(FavoritoEstabelecimento(usuario_id=usuario.id, estabelecimento_id=estabelecimento_id))
    db.commit()


@router.delete("/favoritos/{estabelecimento_id}", status_code=204)
def desfavoritar(estabelecimento_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    db.query(FavoritoEstabelecimento).filter_by(usuario_id=usuario.id, estabelecimento_id=estabelecimento_id).delete()
    db.commit()


class LembreteIn(BaseModel):
    churrasco_id: int = Field(gt=0)
    quando: datetime


@router.post("/lembretes", status_code=201)
def criar_lembrete(payload: LembreteIn, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    if payload.quando.tzinfo is None:
        raise HTTPException(422, detail="Informe a data com fuso horário.")
    quando = payload.quando.astimezone(UTC).replace(tzinfo=None)
    if not agora() < quando <= agora() + timedelta(days=90):
        raise HTTPException(422, detail="Agende um lembrete futuro até 90 dias.")
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    e = db.query(Churrasco).filter_by(id=payload.churrasco_id, usuario_id=usuario.id).first()
    if not e:
        raise HTTPException(404, detail="Evento não encontrado.")
    if db.query(LembreteEvento).filter_by(usuario_id=usuario.id).count() >= 20:
        raise HTTPException(409, detail="Limite de 20 lembretes ativos atingido.")
    tarefa = enfileirar(db, "email", f"lembrete:{usuario.id}:{e.id}:{quando.isoformat()}",
        {"destino": usuario.email, "assunto": "Seu lembrete de churrasco",
         "corpo": "Você pediu um lembrete para revisar seu planejamento no ChurrasPlan."}, quando=quando, usuario_id=usuario.id)
    antigo = db.query(LembreteEvento).filter_by(usuario_id=usuario.id, tarefa_id=tarefa.id).first()
    if antigo:
        return {"id": antigo.id, "quando": antigo.quando}
    lembrete = LembreteEvento(usuario_id=usuario.id, churrasco_id=e.id, tarefa_id=tarefa.id, quando=quando)
    db.add(lembrete); db.commit()
    return {"id": lembrete.id, "quando": quando}


@router.get("/lembretes")
def lembretes(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return [{"id": r.id, "churrasco_id": r.churrasco_id, "quando": r.quando}
            for r in db.query(LembreteEvento).filter_by(usuario_id=usuario.id).all()]


@router.delete("/lembretes/{lembrete_id}", status_code=204)
def cancelar_lembrete(lembrete_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    r = db.query(LembreteEvento).filter_by(id=lembrete_id, usuario_id=usuario.id).first()
    if not r:
        raise HTTPException(404, detail="Lembrete não encontrado.")
    tarefa = db.get(TarefaOutbox, r.tarefa_id) if r.tarefa_id else None
    if tarefa and tarefa.status == "processando":
        raise HTTPException(409, detail="Lembrete já está sendo enviado.")
    if tarefa and tarefa.status in {"pendente", "falhou"}:
        tarefa.status, tarefa.payload_cifrado = "cancelado", ""
    db.delete(r); db.commit()
