"""Seleção explícita e autorização server-side de tenant B2B.

Nenhum org_id enviado pelo browser confere acesso por si só. Todo acesso é
validado na tabela de membros ativos, ou pelo papel admin global.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Organizacao, OrganizacaoMembro, Usuario

PAPEIS_EDICAO = {"proprietario", "gestor", "editor"}


def garantir_organizacao_inicial(db: Session, usuario: Usuario) -> Organizacao:
    # Serializa duas ativações simultâneas no MySQL. Não atribui organizações
    # administrativas automaticamente nem aceita migração de dados por request.
    db.query(Usuario).filter(Usuario.id == usuario.id).with_for_update().one()
    membro = (
        db.query(OrganizacaoMembro)
        .join(Organizacao)
        .filter(OrganizacaoMembro.usuario_id == usuario.id,
                OrganizacaoMembro.ativo.is_(True),
                Organizacao.ativo.is_(True))
        .order_by(OrganizacaoMembro.id)
        .first()
    )
    if membro:
        return membro.organizacao

    org = Organizacao(slug=f"parceiro-{usuario.id}", nome=f"{usuario.nome[:125]} - Parceiro")
    db.add(org)
    db.flush()
    db.add(OrganizacaoMembro(
        organizacao_id=org.id, usuario_id=usuario.id, papel="proprietario", ativo=True
    ))
    db.flush()
    return org


def selecionar_organizacao(
    db: Session, usuario: Usuario, org_id: int | None, *, editar: bool = False
) -> Organizacao | None:
    """Admin sem header mantém seu comportamento global legado.

    Parceiro sem organização ativa falha fechado. Se tiver várias organizações,
    o header X-Organizacao-ID é obrigatório em todas as operações do painel.
    """
    if usuario.papel == "admin":
        if org_id is None:
            return None
        org = db.get(Organizacao, org_id)
        if not org or not org.ativo:
            raise HTTPException(status_code=404, detail="Organização não encontrada.")
        return org

    query = (
        db.query(OrganizacaoMembro)
        .join(Organizacao)
        .filter(OrganizacaoMembro.usuario_id == usuario.id,
                OrganizacaoMembro.ativo.is_(True),
                Organizacao.ativo.is_(True))
    )
    if org_id is not None:
        query = query.filter(OrganizacaoMembro.organizacao_id == org_id)
    membros = query.order_by(OrganizacaoMembro.id).limit(2).all()
    if not membros:
        raise HTTPException(status_code=404, detail="Organização não encontrada para esta conta.")
    if org_id is None and len(membros) > 1:
        raise HTTPException(
            status_code=409,
            detail="Selecione a organização usando o cabeçalho X-Organizacao-ID.",
        )
    membro = membros[0]
    if editar and membro.papel not in PAPEIS_EDICAO:
        raise HTTPException(status_code=403, detail="Sem permissão de edição nesta organização.")
    return membro.organizacao
