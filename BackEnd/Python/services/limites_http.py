"""Limite por IP e classe de operação, compartilhado entre processos MySQL."""
import time
from collections import OrderedDict
from threading import Lock
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from config import settings
from database.connection import get_db
from models import ContadorRequisicao
from services.seguranca import chave_rate_limit
_health_lock = Lock()
_health_contadores = OrderedDict()


def limitar_http(request: Request, db: Session = Depends(get_db)) -> None:
    if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
        return
    if request.url.path.startswith("/api/health"):
        escopo, limite = "health", settings.RATE_LIMIT_READ_PER_MINUTE
        chave = (chave_rate_limit(request, "http:health"), int(time.time()) // 60)
        with _health_lock:
            total = _health_contadores.get(chave, 0) + 1
            _health_contadores[chave] = total
            while len(_health_contadores) > 1024:
                _health_contadores.popitem(last=False)
        if total > limite:
            raise HTTPException(429, detail="Limite de verificação de saúde atingido.", headers={"Retry-After": "60"})
        # Liveness funciona sem banco; readiness fará o SELECT 1 e retorna 503.
        return
    elif request.url.path.startswith("/api/auth") and request.method != "GET":
        escopo, limite = "auth", settings.RATE_LIMIT_AUTH_PER_MINUTE
    elif request.method not in {"GET", "HEAD"} and any(part in request.url.path for part in (
        "transferir-propriedade", "organizacao/encerrar", "/privacidade/minha-conta", "/reprocessar", "/concessao")):
        escopo, limite = "sensivel", settings.RATE_LIMIT_SENSITIVE_PER_MINUTE
    elif request.method in {"GET", "HEAD"}:
        escopo, limite = "leitura", settings.RATE_LIMIT_READ_PER_MINUTE
    else:
        escopo, limite = "escrita", settings.RATE_LIMIT_WRITE_PER_MINUTE
    chave, janela = chave_rate_limit(request, "http:" + escopo), int(time.time()) // 60
    valores = dict(chave=chave, janela=janela, quantidade=1)
    if db.bind.dialect.name == "mysql":
        stmt = mysql_insert(ContadorRequisicao).values(**valores)
        stmt = stmt.on_duplicate_key_update(quantidade=ContadorRequisicao.quantidade + 1)
    else:
        stmt = sqlite_insert(ContadorRequisicao).values(**valores)
        stmt = stmt.on_conflict_do_update(index_elements=["chave", "janela"], set_={"quantidade": ContadorRequisicao.quantidade + 1})
    db.execute(stmt)
    total = db.query(ContadorRequisicao.quantidade).filter_by(chave=chave, janela=janela).scalar()
    db.commit()
    if total > limite:
        raise HTTPException(429, detail="Limite de requisições atingido. Tente novamente em um minuto.", headers={"Retry-After": str(60 - int(time.time()) % 60)})
