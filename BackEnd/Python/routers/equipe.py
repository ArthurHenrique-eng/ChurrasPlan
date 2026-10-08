"""API de equipe B2B: RBAC local, convites one-time e auditoria."""
import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from models import ConviteOrganizacao, Organizacao, OrganizacaoMembro, Usuario
from schemas.organizacoes import AtualizarPapelMembro, ConviteOrganizacaoAceitar, ConviteOrganizacaoCreate
from services.auth import agora, enviar_email, exigir_papeis, hash_token, novo_segredo, usuario_atual_com_csrf
from services.equipe_organizacao import (
    VALIDADE_CONVITE_DIAS, bloquear_organizacao, exigir_gestao,
    exigir_papel_gerenciavel, garantir_vaga, normalizar_email_convite,
    registrar_acao, resumo_equipe,
)
from services.organizacoes import selecionar_organizacao

router = APIRouter(prefix="/api/parceiro", tags=["equipe-organizacao"])


def _membro_out(m: OrganizacaoMembro) -> dict:
    return {"id": m.id, "usuario_id": m.usuario_id, "nome": m.usuario.nome,
            "email": m.usuario.email, "papel": m.papel, "ativo": m.ativo}


@router.get("/equipe/membros")
def listar_membros(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = selecionar_organizacao(db, usuario, organizacao_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização.")
    # Lista de emails da equipe é visível apenas a gestores/proprietários reais.
    exigir_gestao(db, usuario, org.id)
    return [_membro_out(m) for m in db.query(OrganizacaoMembro).filter_by(
        organizacao_id=org.id, ativo=True
    ).order_by(OrganizacaoMembro.id).all()]


@router.get("/equipe/convites")
def listar_convites(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = selecionar_organizacao(db, usuario, organizacao_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização.")
    exigir_gestao(db, usuario, org.id)
    convites = db.query(ConviteOrganizacao).filter(
        ConviteOrganizacao.organizacao_id == org.id,
        ConviteOrganizacao.usado_em.is_(None),
        ConviteOrganizacao.revogado_em.is_(None),
        ConviteOrganizacao.expira_em > agora(),
    ).order_by(ConviteOrganizacao.id.desc()).all()
    return [{"id": c.id, "email": c.email, "papel": c.papel,
             "expira_em": c.expira_em.isoformat()} for c in convites]


@router.post("/equipe/convites", status_code=201)
def convidar(
    payload: ConviteOrganizacaoCreate,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = selecionar_organizacao(db, usuario, organizacao_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização.")
    org, ator = exigir_gestao(db, usuario, org.id)
    exigir_papel_gerenciavel(ator, payload.papel)
    email = normalizar_email_convite(payload.email)
    membro = db.query(OrganizacaoMembro).join(Usuario).filter(
        OrganizacaoMembro.organizacao_id == org.id,
        OrganizacaoMembro.ativo.is_(True), Usuario.email == email,
    ).first()
    if membro:
        raise HTTPException(status_code=409, detail="Este e-mail já participa da organização.")
    pendente = db.query(ConviteOrganizacao).filter(
        ConviteOrganizacao.organizacao_id == org.id,
        ConviteOrganizacao.email == email,
        ConviteOrganizacao.usado_em.is_(None),
        ConviteOrganizacao.revogado_em.is_(None),
        ConviteOrganizacao.expira_em > agora(),
    ).first()
    if pendente:
        raise HTTPException(status_code=409, detail="Já existe um convite ativo para este e-mail.")
    garantir_vaga(db, org)
    if settings.APP_ENV == "production" and not settings.SMTP_HOST:
        raise HTTPException(status_code=503, detail="Convites por e-mail não estão configurados.")
    token = novo_segredo(32)
    c = ConviteOrganizacao(
        organizacao_id=org.id, email=email, papel=payload.papel,
        token_hash=hash_token(token), criado_por_usuario_id=usuario.id,
        expira_em=agora() + timedelta(days=VALIDADE_CONVITE_DIAS),
    )
    db.add(c)
    db.flush()
    link = f"{settings.PUBLIC_APP_URL.rstrip('/')}/parceiro.html?convite={quote(token)}"
    if settings.SMTP_HOST:
        try:
            enviado = enviar_email(
                email, f"Convite para {org.nome} — ChurrasPlan",
                f"Você recebeu um convite para a equipe {org.nome}.\\n"
                f"Entre com a conta associada a {email} (ou crie sua conta).\\n"
                f"O convite expira em {VALIDADE_CONVITE_DIAS} dias.\\n\\n{link}\\n",
            )
        except (OSError, RuntimeError) as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail="Não foi possível enviar o convite.") from exc
        if not enviado:
            db.rollback()
            raise HTTPException(status_code=503, detail="Serviço de e-mail indisponível.")
    registrar_acao(db, org.id, usuario.id, "convite_criado",
                   detalhes={"convite_id": c.id, "papel": payload.papel})
    db.commit()
    return {"id": c.id, "email": email, "papel": c.papel,
            "expira_em": c.expira_em.isoformat(), "enviado": bool(settings.SMTP_HOST),
            "dev_token": token if settings.APP_ENV != "production" else None}


@router.delete("/equipe/convites/{convite_id}")
def revogar_convite(
    convite_id: int,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = selecionar_organizacao(db, usuario, organizacao_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização.")
    org, ator = exigir_gestao(db, usuario, org.id)
    convite = db.query(ConviteOrganizacao).filter_by(
        id=convite_id, organizacao_id=org.id
    ).with_for_update().first()
    if not convite or convite.usado_em or convite.revogado_em:
        raise HTTPException(status_code=404, detail="Convite ativo não encontrado.")
    exigir_papel_gerenciavel(ator, convite.papel, convite.papel)
    convite.revogado_em = agora()
    registrar_acao(db, org.id, usuario.id, "convite_revogado",
                   detalhes={"convite_id": convite.id})
    db.commit()
    return {"mensagem": "Convite revogado."}


@router.post("/convites/aceitar")
def aceitar_convite(
    payload: ConviteOrganizacaoAceitar,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    convite = db.query(ConviteOrganizacao).filter_by(
        token_hash=hash_token(payload.token)
    ).first()
    if not convite:
        raise HTTPException(status_code=404, detail="Convite inválido ou expirado.")
    org = bloquear_organizacao(db, convite.organizacao_id)
    convite = db.query(ConviteOrganizacao).filter_by(id=convite.id).with_for_update().one()
    if (convite.usado_em is not None or convite.revogado_em is not None
            or convite.expira_em <= agora() or not usuario.ativo
            or convite.email != usuario.email.strip().lower()):
        raise HTTPException(status_code=404, detail="Convite inválido ou expirado.")
    membro = db.query(OrganizacaoMembro).filter_by(
        organizacao_id=org.id, usuario_id=usuario.id
    ).with_for_update().first()
    if membro and membro.ativo:
        raise HTTPException(status_code=409, detail="Você já integra esta organização.")
    garantir_vaga(db, org, convite_consumido_id=convite.id)
    if membro is None:
        membro = OrganizacaoMembro(organizacao_id=org.id, usuario_id=usuario.id,
                                  papel=convite.papel, ativo=True)
        db.add(membro)
    else:
        membro.ativo = True
        membro.papel = convite.papel
    if usuario.papel == "usuario":
        usuario.papel = "parceiro"
    convite.usado_em = agora()
    registrar_acao(db, org.id, usuario.id, "convite_aceito",
                   alvo_id=usuario.id, detalhes={"convite_id": convite.id, "papel": convite.papel})
    db.commit()
    return {"organizacao_id": org.id, "organizacao": org.nome,
            "papel": membro.papel, "mensagem": "Convite aceito com sucesso."}


@router.patch("/equipe/membros/{usuario_id}")
def alterar_papel_membro(
    usuario_id: int, payload: AtualizarPapelMembro,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = selecionar_organizacao(db, usuario, organizacao_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização.")
    org, ator = exigir_gestao(db, usuario, org.id)
    if usuario_id == usuario.id:
        raise HTTPException(status_code=422, detail="Não é permitido alterar o próprio papel.")
    alvo = db.query(OrganizacaoMembro).filter_by(
        organizacao_id=org.id, usuario_id=usuario_id, ativo=True
    ).with_for_update().first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Membro não encontrado.")
    exigir_papel_gerenciavel(ator, payload.papel, alvo.papel)
    anterior = alvo.papel
    alvo.papel = payload.papel
    registrar_acao(db, org.id, usuario.id, "membro_papel_alterado", usuario_id,
                   {"antes": anterior, "depois": payload.papel})
    db.commit()
    return _membro_out(alvo)


@router.delete("/equipe/membros/{usuario_id}")
def remover_membro(
    usuario_id: int,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = selecionar_organizacao(db, usuario, organizacao_id)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização.")
    org, ator = exigir_gestao(db, usuario, org.id)
    if usuario_id == usuario.id:
        raise HTTPException(status_code=422, detail="Não é permitido remover a si mesmo.")
    alvo = db.query(OrganizacaoMembro).filter_by(
        organizacao_id=org.id, usuario_id=usuario_id, ativo=True
    ).with_for_update().first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Membro não encontrado.")
    exigir_papel_gerenciavel(ator, "leitor", alvo.papel)
    # Conta global permanece ativa e dados legados B2C/B2B são preservados.
    alvo.ativo = False
    registrar_acao(db, org.id, usuario.id, "membro_removido", usuario_id,
                   {"papel_anterior": alvo.papel})
    db.commit()
    return {"mensagem": "Acesso à organização revogado."}
