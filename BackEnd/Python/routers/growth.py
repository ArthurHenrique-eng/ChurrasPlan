import secrets
import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from config import settings
from database.connection import get_db
from models import (LeadComercial, AtividadeLead, Usuario, Organizacao, IndicacaoUsuario, AtribuicaoCadastro,
    EventoProduto, FeedbackParceiro, CustoOperacao, Estabelecimento, Churrasco, Preco, AssinaturaOrganizacao, AssinaturaStripeUsuario)
from services.auth import usuario_atual, usuario_atual_com_csrf, exigir_papeis, normalizar_email, validar_email_simples, hash_token, agora
from services.organizacoes import selecionar_organizacao
from services.seguranca import registrar_auditoria, verificar_limite, registrar_evento
from services.analytics import EVENTOS_PUBLICOS, registrar_produto

router = APIRouter(prefix="/api/growth", tags=["growth"])
admin_router = APIRouter(prefix="/api/admin/growth", tags=["growth administrativo"])


class LeadIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=160)
    empresa: str = Field(min_length=2, max_length=150)
    tipo_estabelecimento: Literal["acougue", "mercado", "supermercado", "buffet", "churrasqueiro", "outro"]
    cidade: str = Field(min_length=2, max_length=120)
    ciente_privacidade: Literal[True]
    marketing: bool = False
    utm_source: str | None = Field(None, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    utm_medium: str | None = Field(None, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    utm_campaign: str | None = Field(None, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    site: str = Field(default="", max_length=100)  # honeypot

    @field_validator("email")
    @classmethod
    def email_valido(cls, value):
        value = normalizar_email(value)
        if not validar_email_simples(value):
            raise ValueError("E-mail inválido")
        return value


@router.post("/leads", status_code=202)
def criar_lead(payload: LeadIn, request: Request, db: Session = Depends(get_db)):
    chave = verificar_limite(db, request, tipo="lead", limite=5)
    registrar_evento(db, tipo="lead", chave_hash=chave, sucesso=True)
    if not payload.site:
        existente = db.query(LeadComercial).filter_by(email=payload.email, empresa=payload.empresa.strip()).first()
        if not existente:
            lead = LeadComercial(nome=payload.nome.strip(), email=payload.email, empresa=payload.empresa.strip(),
                tipo_estabelecimento=payload.tipo_estabelecimento, cidade=payload.cidade.strip(), marketing_concedido=payload.marketing,
                privacidade_versao=settings.PRIVACY_VERSION, descadastro_hash=hash_token(secrets.token_urlsafe(32)),
                utm={k: v for k, v in payload.model_dump().items() if k.startswith("utm_") and v})
            db.add(lead)
            db.flush()
            lead.descadastro_hash = hash_token(token_descadastro(lead.id))
            db.add(AtividadeLead(lead_id=lead.id, tipo="interesse_solicitado"))
            registrar_produto(db, "lead_criado", str(lead.id), {"segmento": "b2b", "origem": "parceiros"})
    db.commit()
    return {"mensagem": "Interesse recebido. Seus dados serão usados para responder à sua solicitação."}


class DescadastroIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


@router.post("/marketing/descadastrar")
def descadastrar(payload: DescadastroIn, db: Session = Depends(get_db)):
    lead = db.query(LeadComercial).filter_by(descadastro_hash=hash_token(payload.token)).first()
    if lead:
        lead.marketing_concedido, lead.marketing_revogado_em = False, agora()
        db.commit()
    return {"mensagem": "Preferência de descadastro processada."}


class EventoIn(BaseModel):
    evento: str = Field(max_length=60)
    sessao: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    consentimento: Literal[True]
    origem: Literal["home", "planejamento", "resultado", "convite", "parceiros", "onde_comprar", "organico", "indicacao", "direto"] = "direto"


@router.post("/eventos", status_code=204)
def evento_publico(payload: EventoIn, db: Session = Depends(get_db)):
    if payload.evento not in EVENTOS_PUBLICOS:
        raise HTTPException(422, detail="Evento não permitido no navegador.")
    registrar_produto(db, payload.evento, f"{agora().date()}:{payload.sessao}", {"origem": payload.origem, "segmento": "b2c"})
    db.commit()


class ConsentimentoIndicacao(BaseModel):
    consentimento: Literal[True]


@router.post("/indicacoes")
def criar_indicacao(payload: ConsentimentoIndicacao, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    db.query(Usuario).filter_by(id=usuario.id).with_for_update().one()
    registro = db.get(IndicacaoUsuario, usuario.id)
    if not registro:
        registro = IndicacaoUsuario(usuario_id=usuario.id, codigo=secrets.token_urlsafe(24))
        db.add(registro)
        db.commit()
    return {"link": settings.PUBLIC_APP_URL.rstrip("/") + "/index.html?ref=" + registro.codigo,
            "cadastros_atribuidos": db.query(AtribuicaoCadastro).filter_by(indicador_id=usuario.id).count()}


class LeadAtualizar(BaseModel):
    status: Literal["novo", "contatado", "qualificado", "piloto", "convertido", "encerrado"]
    nota: str | None = Field(None, max_length=800)
    organizacao_id: int | None = Field(None, gt=0)


def token_descadastro(lead_id: int) -> str:
    return hmac.new(settings.SECURITY_PEPPER.encode(), f"descadastro-lead:{lead_id}".encode(), hashlib.sha256).hexdigest()


def lead_out(lead, db):
    return {"id": lead.id, "nome": lead.nome, "email": lead.email, "empresa": lead.empresa, "cidade": lead.cidade,
            "tipo": lead.tipo_estabelecimento, "status": lead.status, "marketing": lead.marketing_concedido,
            "organizacao_id": lead.organizacao_id, "criado_em": lead.criado_em, "utm": lead.utm,
            "descadastro_url": settings.PUBLIC_APP_URL.rstrip("/") + "/preferencias.html?token=" + token_descadastro(lead.id) if lead.marketing_concedido else None,
            "atividades": [{"tipo": a.tipo, "nota": a.nota, "criado_em": a.criado_em}
                for a in db.query(AtividadeLead).filter_by(lead_id=lead.id).order_by(AtividadeLead.id).limit(100)]}


@admin_router.get("/leads")
def listar_leads(status: str | None = None, offset: int = Query(0, ge=0), admin: Usuario = Depends(exigir_papeis("admin")), db: Session = Depends(get_db)):
    query = db.query(LeadComercial)
    if status:
        query = query.filter_by(status=status)
    return [lead_out(l, db) for l in query.order_by(LeadComercial.id.desc()).offset(offset).limit(50)]


@admin_router.patch("/leads/{lead_id}")
def atualizar_lead(lead_id: int, payload: LeadAtualizar, admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)), db: Session = Depends(get_db)):
    lead = db.query(LeadComercial).filter_by(id=lead_id).with_for_update().first()
    if not lead:
        raise HTTPException(404, detail="Lead não encontrado.")
    if payload.status == "convertido":
        org = db.get(Organizacao, payload.organizacao_id) if payload.organizacao_id else None
        if not org or not org.ativo:
            raise HTTPException(422, detail="Vincule uma organização ativa para concluir a conversão.")
        lead.organizacao_id = org.id
    lead.status = payload.status
    db.add(AtividadeLead(lead_id=lead.id, admin_id=admin.id, tipo=payload.status, nota=payload.nota))
    registrar_auditoria(db, admin, acao="lead_atualizado", entidade="leads_comerciais", entidade_id=lead.id, detalhes={"status": payload.status})
    db.commit()
    return lead_out(lead, db)


class FeedbackIn(BaseModel):
    nota: int = Field(ge=1, le=5)
    comentario: str | None = Field(None, max_length=800)
    disposicao_pagar: Decimal | None = Field(None, ge=0, le=100000, decimal_places=2)


@router.post("/feedback", status_code=201)
def feedback(payload: FeedbackIn, usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
             oid: int | None = Header(None, alias="X-Organizacao-ID"), db: Session = Depends(get_db)):
    org = selecionar_organizacao(db, usuario, oid)
    if org is None:
        raise HTTPException(422, detail="Selecione uma organização.")
    registro = FeedbackParceiro(organizacao_id=org.id, **payload.model_dump())
    db.add(registro); db.flush()
    registrar_produto(db, "feedback_recebido", str(registro.id), {"segmento": "b2b"})
    db.commit()
    return {"mensagem": "Feedback registrado."}


@admin_router.get("/dashboard")
def dashboard(dias: int = Query(30, ge=1, le=90), admin: Usuario = Depends(exigir_papeis("admin")), db: Session = Depends(get_db)):
    desde = agora() - timedelta(days=dias)
    eventos = dict(db.query(EventoProduto.evento, func.count(EventoProduto.id)).filter(EventoProduto.criado_em >= desde).group_by(EventoProduto.evento).all())
    usuarios = db.query(Usuario).filter(Usuario.ativo.is_(True)).count()
    ativos = db.query(Churrasco.usuario_id).filter(Churrasco.usuario_id.is_not(None), Churrasco.criado_em >= desde).distinct().count()
    b2b = db.query(AssinaturaOrganizacao).all()
    b2c = db.query(AssinaturaStripeUsuario).all()
    from services.billing import assinatura_efetiva
    from services.billing_usuario import assinatura_usuario_efetiva
    pro = sum(assinatura_efetiva(s) and s.plano_slug == "pro" for s in b2b)
    business = sum(assinatura_efetiva(s) and s.plano_slug == "business" for s in b2b)
    premium = sum(assinatura_usuario_efetiva(s) for s in b2c)
    return {"periodo_dias": dias, "desde_utc": desde, "eventos": eventos, "usuarios_ativos": usuarios,
        "usuarios_com_evento_no_periodo": ativos, "ativacao_evento_pct": round(100 * ativos / usuarios, 2) if usuarios else None,
        "leads": db.query(LeadComercial).filter(LeadComercial.criado_em >= desde).count(),
        "parceiros_ativos": db.query(Organizacao).filter_by(ativo=True).count(),
        "estabelecimentos_publicados": db.query(Estabelecimento).filter_by(ativo=True, parceiro_verificado=True).count(),
        "feedbacks_piloto": db.query(FeedbackParceiro).count(),
        "assinaturas_sandbox": {"pro": pro, "business": business, "premium": premium},
        "mrr_real": None, "arr_real": None, "cac_real": None, "ltv_real": None, "churn_financeiro": None,
        "limitacoes": ["Eventos do navegador dependem de consentimento e são deduplicados por dia.",
            "Ativação: usuários ativos com evento no período / usuários ativos cadastrados.",
            "Billing está em sandbox; dados de teste não representam receita real.",
            "CAC/LTV/churn exigem coortes, clientes pagantes e custos confiáveis."]}


class CustoIn(BaseModel):
    competencia: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    categoria: Literal["infraestrutura", "ia", "mapas", "smtp", "marketing", "transacoes", "outros"]
    valor: Decimal = Field(ge=0, le=10000000, decimal_places=2)


@admin_router.post("/custos", status_code=201)
def custo(payload: CustoIn, admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)), db: Session = Depends(get_db)):
    registro = CustoOperacao(**payload.model_dump())
    db.add(registro); db.flush()
    registrar_auditoria(db, admin, acao="custo_registrado", entidade="custos_operacao", entidade_id=registro.id)
    db.commit()
    return {"id": registro.id}


@admin_router.get('/custos')
def custos(competencia: str = Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),
           admin: Usuario = Depends(exigir_papeis('admin')), db: Session = Depends(get_db)):
    linhas=db.query(CustoOperacao).filter_by(competencia=competencia).order_by(CustoOperacao.id).all()
    return {'competencia':competencia,'total_declarado':sum((c.valor for c in linhas),Decimal('0')),
            'itens':[{'id':c.id,'categoria':c.categoria,'valor':c.valor} for c in linhas],
            'observacao':'Custos informados pelo administrador; não são dados automaticamente conciliados com documentos financeiros.'}


class CenariosIn(BaseModel):
    ticket_mensal: Decimal = Field(gt=0, le=100000, decimal_places=2)
    custo_fixo_mensal: Decimal = Field(ge=0, le=10000000, decimal_places=2)
    custo_variavel_cliente: Decimal = Field(ge=0, le=100000, decimal_places=2)
    clientes_conservador: int = Field(ge=0, le=100000)
    clientes_base: int = Field(ge=0, le=100000)
    clientes_otimista: int = Field(ge=0, le=100000)


@admin_router.post('/cenarios')
def cenarios(payload: CenariosIn, admin: Usuario = Depends(exigir_papeis('admin', mutacao=True))):
    linhas=[]
    for nome,n in [('conservador',payload.clientes_conservador),('base',payload.clientes_base),('otimista',payload.clientes_otimista)]:
        receita=n*payload.ticket_mensal;custos=payload.custo_fixo_mensal+n*payload.custo_variavel_cliente
        linhas.append({'cenario':nome,'clientes_hipoteticos':n,'mrr_hipotetico':receita,'arr_hipotetico':12*receita,
                       'custos_hipoteticos':custos,'resultado_mensal_hipotetico':receita-custos})
    return {'hipoteses':payload.model_dump(mode='json'),'cenarios':linhas,
            'observacao':'Simulação, não receita real. Inclua impostos, taxas, inadimplência e aquisição nos custos quando aplicáveis. CAC/LTV reais exigem dados confiáveis.'}
