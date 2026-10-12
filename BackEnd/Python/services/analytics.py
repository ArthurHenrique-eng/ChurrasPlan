"""Catálogo de eventos e propriedades; sem texto livre, localização ou PII."""
import hashlib
import hmac
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from config import settings
from models import EventoProduto
from services.auth import agora

EVENTOS_PUBLICOS = {
    "landing_visualizada", "planejamento_iniciado", "planejamento_concluido", "resultado_visualizado",
    "convite_compartilhado", "onde_comprar_acessado", "parceiro_visualizado", "parceiro_clicado",
}
EVENTOS_SERVIDOR = {"cadastro_criado", "churrasco_salvo", "lead_criado", "parceiro_cadastrado", "organizacao_criada",
    "estabelecimento_enviado", "estabelecimento_aprovado", "primeiro_produto", "primeira_oferta", "assinatura_paga",
    "trial_iniciado", "assinatura_cancelada", "upgrade", "downgrade", "feedback_recebido",
    "primeira_impressao", "primeiro_clique"}
ORIGENS = {"home", "planejamento", "resultado", "convite", "parceiros", "onde_comprar", "organico", "indicacao", "direto"}


def registrar_produto(db, evento: str, chave: str, propriedades: dict | None = None, *, contexto: str | None = None, contexto_tipo: str | None = None):
    if not settings.ANALYTICS_ENABLED:
        return
    if evento not in EVENTOS_PUBLICOS | EVENTOS_SERVIDOR:
        raise ValueError("Evento não permitido")
    props = propriedades or {}
    if set(props) - {"origem", "segmento", "plano"}:
        raise ValueError("Propriedades não permitidas")
    if props.get("origem") and props["origem"] not in ORIGENS:
        raise ValueError("Origem inválida")
    if props.get("segmento") and props["segmento"] not in {"b2c", "b2b"}:
        raise ValueError("Segmento inválido")
    if props.get("plano") and props["plano"] not in {"free", "premium", "pro", "business"}:
        raise ValueError("Plano inválido")
    dedup = hmac.new(settings.SECURITY_PEPPER.encode(), f"{evento}|{chave}".encode(), hashlib.sha256).hexdigest()
    if contexto_tipo not in {None, "sessao_dia", "organizacao"} or bool(contexto) != bool(contexto_tipo):
        raise ValueError("Contexto de funil inválido")
    contexto_hash = hmac.new(settings.SECURITY_PEPPER.encode(), f"funil:{contexto_tipo}:{contexto}".encode(), hashlib.sha256).hexdigest() if contexto else None
    valores = dict(evento=evento, propriedades=props, dedup_hash=dedup, contexto_tipo=contexto_tipo, contexto_hash=contexto_hash)
    if db.bind.dialect.name == "mysql":
        stmt = mysql_insert(EventoProduto).values(**valores)
        stmt = stmt.on_duplicate_key_update(dedup_hash=stmt.inserted.dedup_hash)
    else:
        stmt = sqlite_insert(EventoProduto).values(**valores).on_conflict_do_nothing(index_elements=["dedup_hash"])
    db.execute(stmt)


def atribuir_cadastro(db, usuario, codigo: str | None):
    if not codigo:
        return
    from models import IndicacaoUsuario, AtribuicaoCadastro
    indicacao = db.query(IndicacaoUsuario).filter_by(codigo=codigo).first()
    if indicacao and indicacao.usuario_id != usuario.id:
        db.add(AtribuicaoCadastro(usuario_id=usuario.id, indicador_id=indicacao.usuario_id))


def instalar_hooks():
    """Eventos operacionais na transação da operação que realmente aconteceu."""
    from sqlalchemy import event, inspect, func
    from sqlalchemy.orm import Session
    from models import (Usuario, Organizacao, Churrasco, Estabelecimento, Produto, Preco,
                        AssinaturaOrganizacao, AssinaturaStripeUsuario)

    @event.listens_for(Session, "after_flush")
    def instrumentar(db, contexto):
        for obj in list(db.new):
            if isinstance(obj, Organizacao):
                registrar_produto(db, "organizacao_criada", str(obj.id), {"segmento": "b2b"}, contexto=str(obj.id), contexto_tipo="organizacao")
            elif isinstance(obj, Churrasco) and obj.usuario_id:
                registrar_produto(db, "churrasco_salvo", str(obj.id), {"segmento": "b2c"})
            elif isinstance(obj, Estabelecimento):
                ctx = {"contexto": str(obj.organizacao_id), "contexto_tipo": "organizacao"} if obj.organizacao_id else {}
                registrar_produto(db, "estabelecimento_enviado", str(obj.id), {"segmento": "b2b"}, **ctx)
                if obj.parceiro_verificado:
                    registrar_produto(db, "estabelecimento_aprovado", str(obj.id), {"segmento": "b2b"}, **ctx)
            elif isinstance(obj, Produto) and obj.tipo_produto == "comercial" and obj.organizacao_id:
                primeiro = db.query(func.min(Produto.id)).filter_by(organizacao_id=obj.organizacao_id, tipo_produto="comercial").scalar()
                if obj.id == primeiro:
                    registrar_produto(db, "primeiro_produto", str(obj.organizacao_id), {"segmento": "b2b"}, contexto=str(obj.organizacao_id), contexto_tipo="organizacao")
            elif isinstance(obj, Preco):
                org = db.query(Estabelecimento.organizacao_id).filter_by(id=obj.estabelecimento_id).scalar()
                if org:
                    primeiro = db.query(func.min(Preco.id)).join(Estabelecimento).filter(Estabelecimento.organizacao_id == org).scalar()
                    if obj.id == primeiro:
                        registrar_produto(db, "primeira_oferta", str(org), {"segmento": "b2b"}, contexto=str(org), contexto_tipo="organizacao")
        for obj in list(db.dirty):
            if isinstance(obj, Usuario) and "parceiro" in inspect(obj).attrs.papel.history.added:
                registrar_produto(db, "parceiro_cadastrado", str(obj.id), {"segmento": "b2b"})
            if isinstance(obj, Estabelecimento) and True in inspect(obj).attrs.parceiro_verificado.history.added:
                ctx = {"contexto": str(obj.organizacao_id), "contexto_tipo": "organizacao"} if obj.organizacao_id else {}
                registrar_produto(db, "estabelecimento_aprovado", str(obj.id), {"segmento": "b2b"}, **ctx)
        for obj in list(db.new) + list(db.dirty):
            if isinstance(obj, (AssinaturaOrganizacao, AssinaturaStripeUsuario)) and obj.stripe_subscription_id:
                publico = "b2b" if isinstance(obj, AssinaturaOrganizacao) else "b2c"
                ctx = {"contexto": str(obj.organizacao_id), "contexto_tipo": "organizacao"} if publico == "b2b" else {}
                if obj.status == "active" and obj.periodo_fim_em:
                    registrar_produto(db, "assinatura_paga", f"{obj.stripe_subscription_id}:{obj.periodo_fim_em.isoformat()}", {"segmento": publico, "plano": obj.plano_slug}, **ctx)
                elif obj.status == "canceled":
                    registrar_produto(db, "assinatura_cancelada", str(obj.stripe_subscription_id), {"segmento": publico})
                elif obj.status == "trialing":
                    registrar_produto(db, "trial_iniciado", str(obj.stripe_subscription_id), {"segmento": publico, "plano": obj.plano_slug}, **ctx)
                if obj in db.dirty:
                    mudanca = inspect(obj).attrs.plano_slug.history
                    if mudanca.deleted and mudanca.added:
                        ordem = {"free": 0, "premium": 1, "pro": 1, "business": 2}
                        antes, depois = ordem.get(mudanca.deleted[0], 0), ordem.get(mudanca.added[0], 0)
                        if antes != depois:
                            registrar_produto(db, "upgrade" if depois > antes else "downgrade", f"{obj.stripe_subscription_id}:{obj.plano_slug}:{agora().date()}", {"segmento": publico, "plano": obj.plano_slug}, **ctx)
