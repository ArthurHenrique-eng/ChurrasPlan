"""Outbox transacional. SMTP entrega ao menos uma vez, sem promessa de exactly-once."""
import hashlib
import json
import logging
import secrets
from datetime import timedelta
from sqlalchemy import or_, and_, update
from sqlalchemy.orm import Session
from config import settings
from models import TarefaOutbox, EstadoWorker
from services.auth import agora
from services.criptografia import cifrar, decifrar

logger = logging.getLogger("churrasplan.outbox")


def enfileirar(db: Session, tipo: str, chave: str, payload: dict, *, quando=None, usuario_id=None) -> TarefaOutbox:
    existente = db.query(TarefaOutbox).filter_by(chave=chave).first()
    if existente:
        return existente
    tarefa = TarefaOutbox(tipo=tipo, chave=chave, usuario_id=usuario_id, payload_cifrado=cifrar(json.dumps(payload, ensure_ascii=False)),
                         disponivel_em=quando or agora())
    db.add(tarefa)
    db.flush()
    return tarefa


def enfileirar_email(db: Session, destino: str, assunto: str, corpo: str) -> bool:
    chave = "email:" + hashlib.sha256((destino + "\n" + assunto + "\n" + corpo).encode()).hexdigest()
    from models import Usuario
    usuario_id = db.query(Usuario.id).filter_by(email=destino).scalar()
    enfileirar(db, "email", chave, {"destino": destino, "assunto": assunto, "corpo": corpo}, usuario_id=usuario_id)
    return True


def processar_um(db: Session, *, enviar=None) -> bool:
    momento = agora()
    elegivel = or_(and_(TarefaOutbox.status == "pendente", TarefaOutbox.disponivel_em <= momento),
                   and_(TarefaOutbox.status == "processando", TarefaOutbox.lease_ate < momento))
    tarefa = db.query(TarefaOutbox).filter(elegivel).order_by(TarefaOutbox.id).with_for_update(skip_locked=True).first()
    if not tarefa:
        db.rollback()
        return False
    token = secrets.token_hex(16)
    atualizado = db.execute(update(TarefaOutbox).where(TarefaOutbox.id == tarefa.id, elegivel).values(
        status="processando", lease_ate=momento + timedelta(seconds=settings.OUTBOX_LEASE_SECONDS),
        lease_token=token, tentativas=TarefaOutbox.tentativas + 1))
    if atualizado.rowcount != 1:
        db.rollback()
        return False
    tarefa_id = tarefa.id
    db.commit()  # Entrega nunca mantém lock de banco durante SMTP.
    tarefa = db.get(TarefaOutbox, tarefa_id)
    try:
        dados = json.loads(decifrar(tarefa.payload_cifrado))
        if tarefa.tipo == "billing_webhook":
            from routers.billing import processar_evento_billing
            processar_evento_billing(db, dados)
        elif tarefa.tipo == "email":
            if enviar is None:
                from services.auth import enviar_email
                enviar = enviar_email
            if not enviar(dados["destino"], dados["assunto"], dados["corpo"]):
                raise RuntimeError("SMTP indisponível")
        else:
            raise ValueError("Tipo de tarefa não suportado")
        valores = {"status": "concluido", "concluido_em": agora(), "payload_cifrado": cifrar("{}"), "erro_tipo": None}
    except Exception as exc:
        valores = {"status": "falhou" if tarefa.tentativas >= settings.OUTBOX_MAX_ATTEMPTS else "pendente",
                   "disponivel_em": agora() + timedelta(seconds=min(3600, 30 * 2 ** tarefa.tentativas)),
                   "erro_tipo": type(exc).__name__[:80]}
        logger.warning("outbox_falha", extra={"evento": "outbox_falha", "tipo_erro": type(exc).__name__})
    valores.update(lease_ate=None, lease_token=None)
    db.execute(update(TarefaOutbox).where(TarefaOutbox.id == tarefa_id, TarefaOutbox.lease_token == token).values(**valores))
    db.commit()
    return True


def heartbeat(db: Session, nome: str = "outbox") -> None:
    registro = db.get(EstadoWorker, nome)
    if registro:
        registro.heartbeat_em = agora()
    else:
        db.add(EstadoWorker(nome=nome, heartbeat_em=agora()))
    db.commit()
