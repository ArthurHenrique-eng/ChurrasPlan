from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.connection import get_db
from models import ConsumoAssistente, Usuario
from services.auth import usuario_atual_com_csrf, agora
from services.entitlements_usuario import premium_usuario
from services.assistente import assistir

router = APIRouter(prefix="/api/assistente", tags=["assistente opcional"])


class AssistenteIn(BaseModel):
    texto: str = Field(min_length=5, max_length=1000)


@router.post("/planejamento")
def interpretar(payload: AssistenteIn, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    try:
        resultado = assistir(payload.texto)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    dia = agora().date().isoformat()
    uso = db.get(ConsumoAssistente, (usuario.id, dia))
    limite = 50 if premium_usuario(db, usuario.id) else 10
    if uso and uso.quantidade >= limite:
        raise HTTPException(429, detail="Limite diário do assistente atingido. O formulário manual continua disponível.")
    if uso is None:
        uso = ConsumoAssistente(usuario_id=usuario.id, dia=dia, quantidade=0)
        db.add(uso)
    uso.quantidade += 1
    db.commit()
    return {**resultado, "limite_diario": limite, "uso_diario": uso.quantidade}
