from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.connection import get_db
from models import AuditoriaAdmin, Churrasco, ConcessaoOrganizacao, Estabelecimento, Organizacao, Preco, Produto, Usuario
from schemas.admin import AdminEstabelecimentoUpdate, AdminUsuarioUpdate
from schemas.entitlements import ConcessaoPlanoAdminUpdate
from services.auth import exigir_papeis
from services.entitlements import resumo_entitlements
from services.organizacoes import garantir_organizacao_inicial
from services.seguranca import limpar_eventos_antigos, registrar_auditoria

router = APIRouter(prefix="/api/admin", tags=["administracao"])


@router.get("/dashboard")
def dashboard(admin: Usuario = Depends(exigir_papeis("admin")), db: Session = Depends(get_db)):
    return {
        "usuarios": db.query(Usuario).count(),
        "usuarios_ativos": db.query(Usuario).filter(Usuario.ativo.is_(True)).count(),
        "parceiros": db.query(Usuario).filter(Usuario.papel == "parceiro").count(),
        "estabelecimentos_pendentes": db.query(Estabelecimento).filter(Estabelecimento.parceiro_verificado.is_(False)).count(),
        "churrascos": db.query(Churrasco).count(),
        "produtos": db.query(Produto).count(),
        "ofertas_disponiveis": db.query(Preco).filter(Preco.disponivel.is_(True)).count(),
    }


@router.get("/usuarios")
def listar_usuarios(
    busca: str | None = Query(default=None, max_length=120),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=25, ge=1, le=100),
    admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    q = db.query(Usuario)
    if busca:
        termo = f"%{busca.strip()}%"
        q = q.filter(or_(Usuario.nome.ilike(termo), Usuario.email.ilike(termo)))
    total = q.count()
    usuarios = q.order_by(Usuario.criado_em.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "itens": [
            {
                "id": u.id, "nome": u.nome, "email": u.email, "papel": u.papel,
                "plano": u.plano, "ativo": u.ativo, "email_verificado_em": u.email_verificado_em,
                "criado_em": u.criado_em,
            }
            for u in usuarios
        ],
    }


@router.patch("/usuarios/{usuario_id}")
def atualizar_usuario(
    usuario_id: int,
    payload: AdminUsuarioUpdate,
    admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)),
    db: Session = Depends(get_db),
):
    alvo = db.get(Usuario, usuario_id)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if alvo.id == admin.id and payload.ativo is False:
        raise HTTPException(status_code=422, detail="Você não pode desativar a própria conta administrativa.")
    if alvo.id == admin.id and payload.papel is not None and payload.papel != "admin":
        raise HTTPException(status_code=422, detail="Você não pode remover seu próprio papel de administrador.")
    antes = {"papel": alvo.papel, "ativo": alvo.ativo}
    if payload.papel is not None:
        alvo.papel = payload.papel
        if payload.papel == "parceiro":
            # Promover pelo admin não passa pela rota /parceiro/ativar.
            garantir_organizacao_inicial(db, alvo)
    if payload.ativo is not None:
        alvo.ativo = payload.ativo
    registrar_auditoria(db, admin, acao="usuario_atualizado", entidade="usuario", entidade_id=alvo.id, detalhes={"antes": antes, "depois": {"papel": alvo.papel, "ativo": alvo.ativo}})
    db.commit()
    return {"id": alvo.id, "nome": alvo.nome, "email": alvo.email, "papel": alvo.papel, "ativo": alvo.ativo}


@router.put("/organizacoes/{organizacao_id}/concessao")
def alterar_concessao_organizacao(
    organizacao_id: int,
    payload: ConcessaoPlanoAdminUpdate,
    admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)),
    db: Session = Depends(get_db),
):
    """Concessão administrativa temporária: nunca cria assinatura ou pagamento."""
    org = db.query(Organizacao).filter(
        Organizacao.id == organizacao_id, Organizacao.ativo.is_(True)
    ).with_for_update().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")
    atual = db.query(ConcessaoOrganizacao).filter_by(
        organizacao_id=org.id
    ).with_for_update().first()
    antes = {"plano": atual.plano_slug, "expira_em": atual.expira_em.isoformat()} if atual else None

    if payload.plano == "free":
        if payload.expira_em is not None:
            raise HTTPException(status_code=422, detail="Free não possui validade de concessão.")
        if atual is not None:
            db.delete(atual)
    else:
        expira = payload.expira_em
        if expira is None or expira.tzinfo is None or expira.utcoffset() is None:
            raise HTTPException(
                status_code=422, detail="Pro/Business exige validade com fuso horário."
            )
        agora = datetime.now(UTC)
        if expira <= agora or expira > agora + timedelta(days=366):
            raise HTTPException(status_code=422, detail="Validade deve ser futura e de até 366 dias.")
        expira_utc = expira.astimezone(UTC).replace(tzinfo=None)
        if atual is None:
            atual = ConcessaoOrganizacao(organizacao_id=org.id)
            db.add(atual)
        atual.plano_slug = payload.plano
        atual.origem = "cortesia_admin"
        atual.expira_em = expira_utc
        atual.alterado_por_usuario_id = admin.id

    registrar_auditoria(
        db, admin, acao="concessao_plano_b2b",
        entidade="organizacao", entidade_id=org.id,
        detalhes={"antes": antes, "depois": {
            "plano": payload.plano,
            "expira_em": payload.expira_em.isoformat() if payload.expira_em else None,
            "cobranca": False, "origem": "cortesia_admin" if payload.plano != "free" else "padrao",
        }},
    )
    db.commit()
    return resumo_entitlements(db, org)


@router.get("/estabelecimentos")
def listar_estabelecimentos(
    somente_pendentes: bool = False,
    admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    q = db.query(Estabelecimento)
    if somente_pendentes:
        q = q.filter(Estabelecimento.parceiro_verificado.is_(False))
    return [
        {
            "id": e.id, "nome": e.nome, "tipo": e.tipo, "cidade": e.cidade, "estado": e.estado,
            "parceiro_verificado": e.parceiro_verificado, "ativo": e.ativo,
            "usuario_responsavel_id": e.usuario_responsavel_id,
        }
        for e in q.order_by(Estabelecimento.nome).all()
    ]


@router.patch("/estabelecimentos/{estabelecimento_id}")
def moderar_estabelecimento(
    estabelecimento_id: int,
    payload: AdminEstabelecimentoUpdate,
    admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)),
    db: Session = Depends(get_db),
):
    e = db.get(Estabelecimento, estabelecimento_id)
    if not e:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")
    antes = {"parceiro_verificado": e.parceiro_verificado, "ativo": e.ativo}
    if payload.parceiro_verificado is not None:
        e.parceiro_verificado = payload.parceiro_verificado
    if payload.ativo is not None:
        e.ativo = payload.ativo
    registrar_auditoria(db, admin, acao="estabelecimento_moderado", entidade="estabelecimento", entidade_id=e.id, detalhes={"antes": antes, "depois": {"parceiro_verificado": e.parceiro_verificado, "ativo": e.ativo}})
    db.commit()
    return {"id": e.id, "nome": e.nome, "parceiro_verificado": e.parceiro_verificado, "ativo": e.ativo}


@router.get("/auditoria")
def auditoria(
    limite: int = Query(default=100, ge=1, le=500),
    admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    registros = db.query(AuditoriaAdmin).order_by(AuditoriaAdmin.criado_em.desc()).limit(limite).all()
    return [
        {
            "id": r.id, "admin_usuario_id": r.admin_usuario_id, "acao": r.acao,
            "entidade": r.entidade, "entidade_id": r.entidade_id,
            "detalhes": r.detalhes, "criado_em": r.criado_em,
        }
        for r in registros
    ]


@router.post("/manutencao/limpar-eventos-seguranca")
def limpar_eventos(admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)), db: Session = Depends(get_db)):
    removidos = limpar_eventos_antigos(db)
    registrar_auditoria(db, admin, acao="eventos_seguranca_limpos", entidade="sistema", detalhes={"removidos": removidos})
    db.commit()
    return {"removidos": removidos}
