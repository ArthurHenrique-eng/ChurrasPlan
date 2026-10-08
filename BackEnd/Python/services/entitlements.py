"""Autoridade única para planos B2B e limites de uso.

A existência de assinaturas_usuario, o campo usuarios.plano e os valores de
plano enviados pelo browser NUNCA concedem direitos B2B. Só concessões
administrativas válidas podem elevar Free a Pro/Business até integrar billing.
"""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ConcessaoOrganizacao, Estabelecimento, Organizacao, Preco, Produto, Usuario

# Valores operacionais iniciais, NÃO preços nem ofertas comerciais.
# Contagens incluem dados legados e registros inativos (evita contorno de quota).
LIMITES_PLANOS = {
    "free": {"estabelecimentos": 3, "produtos_comerciais": 100, "ofertas": 2000},
    "pro": {"estabelecimentos": 20, "produtos_comerciais": 1000, "ofertas": 20000},
    "business": {"estabelecimentos": 200, "produtos_comerciais": 10000, "ofertas": 100000},
}
RECURSOS_PLANOS = {
    "free": {"painel_parceiro": True, "dashboard": True, "api": False},
    "pro": {"painel_parceiro": True, "dashboard": True, "api": False},
    "business": {"painel_parceiro": True, "dashboard": True, "api": False},
}


def agora_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def resolver_plano(db: Session, organizacao_id: int, *, bloqueio: bool = False) -> tuple[str, str, datetime | None]:
    consulta = db.query(ConcessaoOrganizacao).filter_by(organizacao_id=organizacao_id)
    if bloqueio:
        consulta = consulta.with_for_update()
    concessao = consulta.first()
    if not concessao:
        return "free", "padrao_gratuito", None
    if (concessao.origem != "cortesia_admin"
            or concessao.plano_slug not in ("pro", "business")
            or concessao.expira_em <= agora_utc()):
        return "free", "concessao_expirada_ou_invalida", None
    return concessao.plano_slug, "cortesia_admin", concessao.expira_em


def _contagem_atual(db: Session, org_id: int, recurso: str, *, bloqueio: bool = False) -> int:
    # SELECT ... FOR UPDATE é leitura corrente no InnoDB; o lock da organização
    # serializa mutações deste tenant e evita snapshots repeatable-read defasados.
    if recurso == "estabelecimentos":
        stmt = select(Estabelecimento.id).where(Estabelecimento.organizacao_id == org_id)
    elif recurso == "produtos_comerciais":
        stmt = select(Produto.id).where(Produto.organizacao_id == org_id,
                                       Produto.tipo_produto == "comercial")
    elif recurso == "ofertas":
        stmt = select(Preco.id).join(Estabelecimento).where(
            Estabelecimento.organizacao_id == org_id
        )
    else:
        raise ValueError("Recurso B2B desconhecido")
    if bloqueio:
        stmt = stmt.with_for_update()
    return len(db.execute(stmt).all())


def resumo_entitlements(db: Session, org: Organizacao) -> dict:
    slug, fonte, validade = resolver_plano(db, org.id)
    return {
        "organizacao_id": org.id,
        "plano": slug,
        "fonte": fonte,
        "expira_em": validade,
        "pagamentos_habilitados": False,
        "checkout_habilitado": False,
        "limites": LIMITES_PLANOS[slug].copy(),
        "uso": {k: _contagem_atual(db, org.id, k) for k in LIMITES_PLANOS["free"]},
        "recursos": RECURSOS_PLANOS[slug].copy(),
    }


def exigir_cota_criacao(
    db: Session, org: Organizacao | None, usuario: Usuario, recurso: str,
) -> None:
    if org is None or usuario.papel == "admin":
        # Operação administrativa global antiga não perde acesso operacional.
        return
    # A transação deve envolver o lock, a contagem, a inserção e um commit.
    atual = db.query(Organizacao).filter_by(id=org.id, ativo=True).with_for_update().first()
    if not atual:
        raise HTTPException(status_code=404, detail="Organização desativada.")
    slug, _, _ = resolver_plano(db, org.id, bloqueio=True)
    limite = LIMITES_PLANOS[slug][recurso]
    uso = _contagem_atual(db, org.id, recurso, bloqueio=True)
    if uso >= limite:
        raise HTTPException(
            status_code=409,
            detail={
                "codigo": "LIMITE_PLANO_ATINGIDO",
                "recurso": recurso,
                "plano": slug,
                "uso": uso,
                "limite": limite,
                "mensagem": "Limite do plano atingido para novas inclusões.",
            },
        )
