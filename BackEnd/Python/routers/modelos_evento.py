"""Modelos reutilizáveis exclusivos Premium; leitura/exclusão preservadas no downgrade."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from database.connection import get_db
from models import Churrasco, ModeloEventoUsuario, Usuario
from schemas.churrasco import ChurrascoCreate, ChurrascoOut
from services.auth import usuario_atual, usuario_atual_com_csrf
from services.entitlements_usuario import exigir_premium_usuario
from services.modelos_usuario import snapshot_modelo

router = APIRouter(prefix="/api/modelos-evento", tags=["modelos-evento-premium"])


class CriarModeloIn(BaseModel):
    churrasco_id: int = Field(gt=0)
    nome: str = Field(min_length=2, max_length=150)


class UsarModeloIn(BaseModel):
    nome: str | None = Field(default=None, max_length=150)


@router.get("")
def listar_modelos(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    registros = db.query(ModeloEventoUsuario).filter_by(usuario_id=usuario.id).order_by(
        ModeloEventoUsuario.id.desc()
    ).all()
    return [{"id": m.id, "nome": m.nome, "criado_em": m.criado_em} for m in registros]


@router.post("", status_code=201)
def criar_modelo(payload: CriarModeloIn, usuario: Usuario = Depends(usuario_atual_com_csrf),
                 db: Session = Depends(get_db)):
    exigir_premium_usuario(db, usuario, "modelos_eventos")
    origem = db.get(Churrasco, payload.churrasco_id)
    if not origem or origem.usuario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Planejamento não encontrado na conta.")
    dados = snapshot_modelo(origem)
    # Antes de persistir, garanta que o snapshot ainda obedece à matemática vigente.
    try:
        ChurrascoCreate.model_validate(dados)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Planejamento original não pode ser convertido em modelo.") from exc
    m = ModeloEventoUsuario(usuario_id=usuario.id, nome=payload.nome.strip(), dados=dados)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id, "nome": m.nome, "criado_em": m.criado_em}


@router.post("/{modelo_id}/usar", response_model=ChurrascoOut, status_code=201)
def usar_modelo(modelo_id: int, payload: UsarModeloIn, usuario: Usuario = Depends(usuario_atual_com_csrf),
               db: Session = Depends(get_db)):
    exigir_premium_usuario(db, usuario, "modelos_eventos")
    m = db.query(ModeloEventoUsuario).filter_by(id=modelo_id, usuario_id=usuario.id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Modelo não encontrado na conta.")
    dados = {**m.dados, "nome": payload.nome or m.nome, "chave_cliente": "modelo-" + secrets.token_hex(12)}
    try:
        validado = ChurrascoCreate.model_validate(dados)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Modelo desatualizado; revise o planejamento de origem.") from exc
    # Reusar o motor determinístico existente, nunca recalcular no navegador.
    from routers.churrascos import _recalcular
    novo = Churrasco(chave_cliente=validado.chave_cliente, usuario_id=usuario.id)
    db.add(novo)
    resultado = _recalcular(db, novo, validado)
    db.commit()
    return resultado


@router.delete("/{modelo_id}", status_code=204)
def excluir_modelo(modelo_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf),
                   db: Session = Depends(get_db)):
    m = db.query(ModeloEventoUsuario).filter_by(id=modelo_id, usuario_id=usuario.id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Modelo não encontrado na conta.")
    db.delete(m)
    db.commit()
    return None
