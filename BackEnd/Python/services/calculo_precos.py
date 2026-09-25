"""Seleção de ofertas atuais e resumo de histórico de preços."""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from models import Preco, Produto


@dataclass
class OfertaAtual:
    preco_id: int
    produto_id: int
    estabelecimento_id: int
    estabelecimento_nome: str
    preco: float
    data_atualizacao: datetime | None
    fonte: str | None


@dataclass
class ResumoPreco:
    produto_id: int
    produto_nome: str
    preco_mais_recente_historico: float | None
    preco_medio_historico: float | None
    preco_minimo_atual: float | None
    preco_maximo_atual: float | None
    quantidade_estabelecimentos: int
    melhor_estabelecimento_id: int | None
    melhor_estabelecimento_nome: str | None


def preco_publicavel(p: Preco) -> bool:
    """Preço que pode aparecer em endpoints/cálculos públicos.

    Ofertas submetidas por parceiro só viram fonte pública depois que o
    estabelecimento é verificado. Fontes internas/importadas não dependem
    desse fluxo de aprovação.
    """
    if p.origem == "referencia_planejamento":
        return False
    return not (p.origem == "manual_parceiro" and not p.estabelecimento.parceiro_verificado)


def oferta_valida(p: Preco, agora: datetime | None = None, incluir_parceiro_nao_verificado: bool = False) -> bool:
    agora = agora or datetime.now(UTC).replace(tzinfo=None)
    if not p.disponivel or p.estoque_status == "indisponivel": return False
    if p.inicio_validade and p.inicio_validade > agora: return False
    if p.fim_validade and p.fim_validade < agora: return False
    if not incluir_parceiro_nao_verificado and not preco_publicavel(p):
        return False
    return bool(p.estabelecimento.ativo)


def listar_ofertas_atuais(db: Session, produto_id: int, *, incluir_parceiro_nao_verificado: bool = False) -> list[Preco]:
    registros = (
        db.query(Preco)
        .filter(Preco.produto_id == produto_id, Preco.disponivel.is_(True))
        .order_by(Preco.estabelecimento_id.asc(), Preco.coletado_em.desc(), Preco.id.desc())
        .all()
    )
    por_estabelecimento: dict[int, Preco] = {}
    for registro in registros:
        if oferta_valida(registro, incluir_parceiro_nao_verificado=incluir_parceiro_nao_verificado):
            por_estabelecimento.setdefault(registro.estabelecimento_id, registro)
    return list(por_estabelecimento.values())


def obter_melhor_oferta_atual(db: Session, produto_id: int) -> OfertaAtual | None:
    atuais = listar_ofertas_atuais(db, produto_id)
    if not atuais: return None
    melhor = min(atuais, key=lambda p: float(p.preco))
    return OfertaAtual(
        preco_id=melhor.id, produto_id=melhor.produto_id, estabelecimento_id=melhor.estabelecimento_id,
        estabelecimento_nome=melhor.estabelecimento.nome, preco=float(melhor.preco),
        data_atualizacao=melhor.data_atualizacao, fonte=melhor.fonte,
    )


def obter_resumo_preco(db: Session, produto_id: int) -> ResumoPreco | None:
    produto = db.get(Produto, produto_id)
    if not produto: return None
    historico = [p for p in db.query(Preco).filter(Preco.produto_id == produto_id).all() if preco_publicavel(p)]
    atuais = listar_ofertas_atuais(db, produto_id)
    if not historico:
        return ResumoPreco(produto.id, produto.nome, None, None, None, None, 0, None, None)
    mais_recente = max(historico, key=lambda p: (p.coletado_em or p.data_atualizacao or datetime.min, p.id))
    valores_hist = [float(p.preco) for p in historico]
    valores_atuais = [float(p.preco) for p in atuais]
    melhor = min(atuais, key=lambda p: float(p.preco)) if atuais else None
    return ResumoPreco(
        produto_id=produto.id, produto_nome=produto.nome,
        preco_mais_recente_historico=float(mais_recente.preco), preco_medio_historico=round(sum(valores_hist) / len(valores_hist), 2),
        preco_minimo_atual=round(min(valores_atuais), 2) if valores_atuais else None,
        preco_maximo_atual=round(max(valores_atuais), 2) if valores_atuais else None,
        quantidade_estabelecimentos=len(atuais), melhor_estabelecimento_id=melhor.estabelecimento_id if melhor else None,
        melhor_estabelecimento_nome=melhor.estabelecimento.nome if melhor else None,
    )


def obter_resumo_preco_por_slug(db: Session, slug: str) -> ResumoPreco | None:
    produto = db.query(Produto).filter(Produto.slug == slug).first()
    return obter_resumo_preco(db, produto.id) if produto else None
