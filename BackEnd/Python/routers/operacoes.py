"""Painel operacional restrito; nunca devolve payloads/segredos da fila."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from config import settings
from database.connection import get_db
from models import TarefaOutbox, EstadoWorker, Usuario
from services.auth import exigir_papeis, agora
from services.observabilidade import metricas_http
from services.seguranca import registrar_auditoria

router = APIRouter(prefix="/api/admin/operacao", tags=["operações"])


@router.get("/metricas")
def metricas(admin: Usuario = Depends(exigir_papeis("admin")), db: Session = Depends(get_db)):
    contagens = dict(db.query(TarefaOutbox.status, func.count(TarefaOutbox.id)).group_by(TarefaOutbox.status).all())
    worker = db.get(EstadoWorker, "outbox")
    ativo = bool(worker and worker.heartbeat_em > agora() - timedelta(seconds=60))
    alertas = []
    if settings.WORKER_REQUIRED and not ativo:
        alertas.append("WORKER_INATIVO")
    if contagens.get("falhou", 0):
        alertas.append("OUTBOX_DEAD_LETTER")
    if db.query(TarefaOutbox).filter(TarefaOutbox.status == "pendente", TarefaOutbox.disponivel_em < agora() - timedelta(minutes=10)).count():
        alertas.append("OUTBOX_ATRASADA")
    return {**metricas_http(), "fila": contagens, "worker_ativo": ativo, "alertas": alertas,
            "observacao": "Métricas HTTP por processo; fila e heartbeat compartilhados no banco."}


@router.get("/tarefas")
def tarefas(admin: Usuario = Depends(exigir_papeis("admin")), db: Session = Depends(get_db)):
    return [{"id": t.id, "tipo": t.tipo, "status": t.status, "tentativas": t.tentativas, "erro_tipo": t.erro_tipo,
             "criado_em": t.criado_em, "disponivel_em": t.disponivel_em}
            for t in db.query(TarefaOutbox).order_by(TarefaOutbox.id.desc()).limit(100)]


@router.post("/tarefas/{tarefa_id}/reprocessar")
def reprocessar(tarefa_id: int, admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)), db: Session = Depends(get_db)):
    tarefa = db.query(TarefaOutbox).filter_by(id=tarefa_id, status="falhou").with_for_update().first()
    if not tarefa:
        raise HTTPException(404, detail="Tarefa falha não encontrada.")
    tarefa.status, tarefa.tentativas, tarefa.disponivel_em = "pendente", 0, agora()
    registrar_auditoria(db, admin, acao="outbox_reprocessada", entidade="tarefas_outbox", entidade_id=tarefa.id)
    db.commit()
    return {"mensagem": "Tarefa agendada para nova tentativa."}
