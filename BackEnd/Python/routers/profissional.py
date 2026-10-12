"""Clientes e propostas do profissional; snapshots não alteram cálculos do planejador."""
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import get_db
from models import ClienteProfissional, PropostaProfissional, Churrasco, Usuario
from services.auth import usuario_atual, usuario_atual_com_csrf
from services.entitlements_usuario import premium_usuario, exigir_premium_usuario

router = APIRouter(prefix="/api/profissional", tags=["profissional"])


def cota(db, usuario, modelo, limite):
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    if not premium_usuario(db, usuario.id) and db.query(modelo).filter_by(usuario_id=usuario.id).with_for_update().count() >= limite:
        raise HTTPException(409, detail={"codigo": "LIMITE_PROFISSIONAL_FREE", "limite": limite,
                                        "mensagem": "Limite gratuito atingido. Os registros existentes continuam acessíveis."})


def cliente_out(c):
    return {"id": c.id, "nome": c.nome, "email": c.email, "telefone": c.telefone}


class ClienteIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str | None = Field(None, max_length=160)
    telefone: str | None = Field(None, max_length=30, pattern=r"^[+0-9() -]+$")


@router.get("/clientes")
def clientes(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return [cliente_out(c) for c in db.query(ClienteProfissional).filter_by(usuario_id=usuario.id).order_by(ClienteProfissional.id).limit(500)]


@router.post("/clientes", status_code=201)
def criar_cliente(payload: ClienteIn, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    cota(db, usuario, ClienteProfissional, 3)
    c = ClienteProfissional(usuario_id=usuario.id, **payload.model_dump())
    db.add(c); db.commit()
    return cliente_out(c)


@router.put("/clientes/{cliente_id}")
def editar_cliente(cliente_id: int, payload: ClienteIn, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    c = db.query(ClienteProfissional).filter_by(id=cliente_id, usuario_id=usuario.id).first()
    if not c:
        raise HTTPException(404, detail="Cliente não encontrado.")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return cliente_out(c)


@router.delete("/clientes/{cliente_id}", status_code=204)
def excluir_cliente(cliente_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    c = db.query(ClienteProfissional).filter_by(id=cliente_id, usuario_id=usuario.id).first()
    if not c:
        raise HTTPException(404, detail="Cliente não encontrado.")
    db.query(PropostaProfissional).filter_by(cliente_id=c.id, usuario_id=usuario.id).update({"cliente_id": None})
    db.delete(c); db.commit()


class PropostaIn(BaseModel):
    chave: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    cliente_id: int = Field(gt=0)
    churrasco_id: int = Field(gt=0)
    titulo: str = Field(min_length=3, max_length=150)
    custos_adicionais: Decimal = Field(default=Decimal("0"), ge=0, le=10000000, decimal_places=2)
    preco_proposto: Decimal = Field(gt=0, le=10000000, decimal_places=2)


def proposta_out(p):
    lucro = p.preco_proposto - p.custo_estimado
    return {"id": p.id, "titulo": p.titulo, "cliente_id": p.cliente_id, "churrasco_id": p.churrasco_id,
            "snapshot": p.snapshot, "custo_estimado": p.custo_estimado, "preco_proposto": p.preco_proposto,
            "resultado_estimado": lucro, "margem_estimada_pct": round(100 * lucro / p.preco_proposto, 2),
            "status": p.status, "criado_em": p.criado_em,
            "observacao": "Proposta comercial baseada em orçamento; não é venda, lucro realizado ou documento fiscal."}


@router.get("/propostas")
def propostas(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return [proposta_out(p) for p in db.query(PropostaProfissional).filter_by(usuario_id=usuario.id).order_by(PropostaProfissional.id.desc()).limit(500)]


@router.post("/propostas", status_code=201)
def criar_proposta(payload: PropostaIn, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    antiga = db.query(PropostaProfissional).filter_by(usuario_id=usuario.id, chave=payload.chave).first()
    if antiga:
        if antiga.snapshot.get("pedido") != payload.model_dump(mode="json"):
            raise HTTPException(409, detail="Chave já utilizada com outro conteúdo.")
        return proposta_out(antiga)
    cota(db, usuario, PropostaProfissional, 5)
    cliente = db.query(ClienteProfissional).filter_by(id=payload.cliente_id, usuario_id=usuario.id).first()
    evento = db.query(Churrasco).filter_by(id=payload.churrasco_id, usuario_id=usuario.id).first()
    if not cliente or not evento:
        raise HTTPException(404, detail="Cliente ou evento não encontrado para esta conta.")
    from routers.churrascos import _itens_persistidos, _montar_out
    resultado = _montar_out(evento, _itens_persistidos(evento))
    if not resultado.estimativa_precos_completa or resultado.custo_total_estimado is None:
        raise HTTPException(409, detail="Complete os preços do planejamento antes de gerar uma proposta com margem.")
    custo = Decimal(str(resultado.custo_total_estimado)) + payload.custos_adicionais
    p = PropostaProfissional(usuario_id=usuario.id, cliente_id=cliente.id, churrasco_id=evento.id, chave=payload.chave,
        titulo=payload.titulo, custo_estimado=custo, preco_proposto=payload.preco_proposto,
        snapshot={"pedido": payload.model_dump(mode="json"), "total_pessoas": evento.total_pessoas,
                  "base_estimativa": resultado.custo_total_estimado,
                  "itens": [i.model_dump(mode="json") for i in resultado.itens]})
    db.add(p); db.commit()
    return proposta_out(p)


class StatusProposta(BaseModel):
    status: Literal["rascunho", "enviada", "aceita", "recusada", "cancelada"]


@router.patch("/propostas/{proposta_id}")
def status_proposta(proposta_id: int, payload: StatusProposta, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    p = db.query(PropostaProfissional).filter_by(id=proposta_id, usuario_id=usuario.id).first()
    if not p:
        raise HTTPException(404, detail="Proposta não encontrada.")
    p.status = payload.status
    db.commit()
    return proposta_out(p)


@router.get("/propostas/{proposta_id}/pdf")
def exportar_proposta(proposta_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    exigir_premium_usuario(db, usuario, "exportacao_profissional")
    p = db.query(PropostaProfissional).filter_by(id=proposta_id, usuario_id=usuario.id).first()
    if not p:
        raise HTTPException(404, detail="Proposta não encontrada.")
    from reportlab.pdfgen import canvas
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.setTitle("Proposta ChurrasPlan")
    for y, texto in [(790, "ChurrasPlan — Proposta comercial"), (755, p.titulo[:80]),
                     (720, f"Participantes: {p.snapshot['total_pessoas']}"), (685, f"Valor proposto: R$ {p.preco_proposto:.2f}"),
                     (650, "Orçamento estimativo. Não representa venda ou documento fiscal.")]:
        pdf.drawString(50, y, texto)
    pdf.save()
    return Response(stream.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="proposta-{p.id}.pdf"'})
