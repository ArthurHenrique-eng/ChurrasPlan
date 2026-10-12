"""Manutenção operacional com retenções explícitas e sem perder tarefas pendentes."""
import time
from datetime import timedelta
from sqlalchemy.orm import Session
from models import ContadorRequisicao, ConsumoAssistente, EventoProduto, MetricaEstabelecimento, LeadComercial, AtividadeLead, TarefaOutbox, LembreteEvento
from config import settings
from services.auth import agora
from services.seguranca import limpar_eventos_antigos


def executar_retencao(db: Session):
    limpar_eventos_antigos(db)
    db.query(ContadorRequisicao).filter(ContadorRequisicao.janela < int(time.time()) // 60 - 1440).delete(synchronize_session=False)
    limite = agora() - timedelta(days=settings.ANALYTICS_RETENTION_DAYS)
    db.query(EventoProduto).filter(EventoProduto.criado_em < limite).delete(synchronize_session=False)
    db.query(MetricaEstabelecimento).filter(MetricaEstabelecimento.criado_em < limite).delete(synchronize_session=False)
    db.query(ConsumoAssistente).filter(ConsumoAssistente.dia < limite.date().isoformat()).delete(synchronize_session=False)
    antigos = db.query(LeadComercial.id).filter(LeadComercial.criado_em < agora() - timedelta(days=settings.LEAD_RETENTION_DAYS), LeadComercial.status != 'convertido').subquery()
    # Explicitamente apaga atividades também em fixtures SQLite sem cascatas.
    db.query(AtividadeLead).filter(AtividadeLead.lead_id.in_(db.query(antigos.c.id))).delete(synchronize_session=False)
    db.query(LeadComercial).filter(LeadComercial.id.in_(db.query(antigos.c.id))).delete(synchronize_session=False)
    db.query(LembreteEvento).filter(LembreteEvento.quando < agora() - timedelta(days=1)).delete(synchronize_session=False)
    db.query(TarefaOutbox).filter(TarefaOutbox.status.in_(['concluido','cancelado']), TarefaOutbox.criado_em < agora() - timedelta(days=7)).delete(synchronize_session=False)
    db.commit()
