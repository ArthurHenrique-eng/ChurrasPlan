"""RBAC B2B restrito, convites one-time por e-mail e vagas de equipe.

Mutações em uma organização serializadas pelo lock FOR UPDATE de organizacoes.
Papéis locais não são inferidos do papel global do usuário ou do header sozinho.
"""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AuditoriaOrganizacao, ConviteOrganizacao, Organizacao, OrganizacaoMembro, Usuario
from services.auth import agora, normalizar_email, validar_email_simples
from services.entitlements import resolver_plano

PAPEIS_ORG = {"proprietario", "gestor", "editor", "leitor"}
PAPEIS_GESTAO = {"proprietario", "gestor"}
LIMITES_MEMBROS = {"free": 3, "pro": 15, "business": 100}
VALIDADE_CONVITE_DIAS = 7


def bloquear_organizacao(db: Session, org_id: int) -> Organizacao:
    org = db.query(Organizacao).filter_by(id=org_id, ativo=True).with_for_update().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")
    return org


def membro_ativo(db: Session, usuario: Usuario, org_id: int) -> OrganizacaoMembro:
    membro = db.query(OrganizacaoMembro).filter_by(
        organizacao_id=org_id, usuario_id=usuario.id, ativo=True
    ).first()
    if not membro or not membro.organizacao.ativo or membro.papel not in PAPEIS_ORG:
        raise HTTPException(status_code=404, detail="Organização não encontrada para esta conta.")
    return membro


def exigir_gestao(db: Session, usuario: Usuario, org_id: int) -> tuple[Organizacao, OrganizacaoMembro]:
    org = bloquear_organizacao(db, org_id)
    membro = membro_ativo(db, usuario, org.id)
    if membro.papel not in PAPEIS_GESTAO:
        raise HTTPException(status_code=403, detail="Somente proprietário ou gestor pode administrar a equipe.")
    return org, membro


def exigir_papel_gerenciavel(ator: OrganizacaoMembro, novo_papel: str, papel_atual: str | None = None) -> None:
    if novo_papel not in PAPEIS_ORG:
        raise HTTPException(status_code=422, detail="Papel organizacional inválido.")
    if ator.papel == "gestor" and (
        novo_papel not in {"editor", "leitor"}
        or (papel_atual is not None and papel_atual not in {"editor", "leitor"})
    ):
        raise HTTPException(status_code=403, detail="Gestor só administra editores e leitores.")


def garantir_vaga(db: Session, org: Organizacao, *, convite_consumido_id: int | None = None) -> dict:
    plano, _, _ = resolver_plano(db, org.id, bloqueio=True)
    limite = LIMITES_MEMBROS[plano]
    membros = int(db.execute(select(func.count(OrganizacaoMembro.id)).where(
        OrganizacaoMembro.organizacao_id == org.id, OrganizacaoMembro.ativo.is_(True)
    ).with_for_update()).scalar_one())
    filtro = [
        ConviteOrganizacao.organizacao_id == org.id,
        ConviteOrganizacao.usado_em.is_(None),
        ConviteOrganizacao.revogado_em.is_(None),
        ConviteOrganizacao.expira_em > agora(),
    ]
    if convite_consumido_id is not None:
        filtro.append(ConviteOrganizacao.id != convite_consumido_id)
    pendentes = int(db.execute(select(func.count(ConviteOrganizacao.id)).where(
        *filtro
    ).with_for_update()).scalar_one())
    if membros + pendentes >= limite:
        raise HTTPException(status_code=409, detail={
            "codigo": "LIMITE_MEMBROS_ATINGIDO", "plano": plano, "limite": limite,
            "ativos": membros, "convites_pendentes": pendentes,
        })
    return {"plano": plano, "limite": limite, "ativos": membros, "convites_pendentes": pendentes}


def resumo_equipe(db: Session, org: Organizacao) -> dict:
    plano, _, _ = resolver_plano(db, org.id)
    membros = db.query(OrganizacaoMembro).filter_by(organizacao_id=org.id, ativo=True).count()
    pendentes = db.query(ConviteOrganizacao).filter(
        ConviteOrganizacao.organizacao_id == org.id,
        ConviteOrganizacao.usado_em.is_(None),
        ConviteOrganizacao.revogado_em.is_(None),
        ConviteOrganizacao.expira_em > agora(),
    ).count()
    return {"ativos": membros, "convites_pendentes": pendentes, "limite": LIMITES_MEMBROS[plano]}


def registrar_acao(db: Session, org_id: int, usuario_id: int, acao: str,
                  alvo_id: int | None = None, detalhes: dict | None = None):
    db.add(AuditoriaOrganizacao(
        organizacao_id=org_id, autor_usuario_id=usuario_id,
        alvo_usuario_id=alvo_id, acao=acao, detalhes=detalhes,
    ))


def normalizar_email_convite(valor: str) -> str:
    email = normalizar_email(valor)
    if not validar_email_simples(email):
        raise HTTPException(status_code=422, detail="Informe um e-mail válido.")
    return email
