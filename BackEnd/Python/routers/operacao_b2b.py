"""Operação B2B: filiais, importação de ofertas CSV e indicadores não financeiros."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import get_db
from models import (Estabelecimento, ImportacaoOfertas, MetricaEstabelecimento,
                    Organizacao, Preco, Produto, Usuario)
from schemas.estabelecimento import EstabelecimentoOut
from schemas.operacao_b2b import FilialMetaUpdate, ImportacaoOfertasCSV
from services.auth import agora, exigir_papeis
from services.entitlements import LIMITES_PLANOS, _contagem_atual, resolver_plano
from services.equipe_organizacao import exigir_gestao
from services.organizacoes import selecionar_organizacao

router = APIRouter(prefix="/api/parceiro", tags=["operacao-b2b"])

COLUNAS_OBRIGATORIAS = {"estabelecimento_id", "produto_id", "preco"}
COLUNAS_PERMITIDAS = COLUNAS_OBRIGATORIAS | {"preco_original", "estoque_status"}
ESTOQUES_VALIDOS = {"disponivel", "baixo", "indisponivel"}
MAX_LINHAS_CSV = 200


def _org(db: Session, usuario: Usuario, org_id: int | None, *, editar=False) -> Organizacao:
    org = selecionar_organizacao(db, usuario, org_id, editar=editar)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização com X-Organizacao-ID.")
    return org


def _filial_out(e: Estabelecimento) -> dict:
    return {
        "id": e.id, "organizacao_id": e.organizacao_id, "nome": e.nome,
        "codigo_filial": e.codigo_filial, "unidade_matriz": e.unidade_matriz,
        "parceiro_verificado": e.parceiro_verificado, "ativo": e.ativo,
        "cidade": e.cidade, "estado": e.estado, "tipo": e.tipo,
    }


@router.get("/filiais")
def listar_filiais(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    filiais = db.query(Estabelecimento).filter_by(organizacao_id=org.id).order_by(
        Estabelecimento.nome, Estabelecimento.id
    ).all()
    return [_filial_out(e) for e in filiais]


@router.patch("/filiais/{estabelecimento_id}")
def editar_filial(
    estabelecimento_id: int,
    payload: FilialMetaUpdate,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    exigir_gestao(db, usuario, org.id)
    loja = db.query(Estabelecimento).filter_by(id=estabelecimento_id, organizacao_id=org.id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Filial não encontrada nesta organização.")
    chaves = payload.model_fields_set
    if "codigo_filial" in chaves:
        codigo = payload.codigo_filial.upper() if payload.codigo_filial else None
        if codigo and db.query(Estabelecimento.id).filter(
            Estabelecimento.organizacao_id == org.id,
            Estabelecimento.codigo_filial == codigo,
            Estabelecimento.id != loja.id,
        ).first():
            raise HTTPException(status_code=409, detail="Código de filial já cadastrado nesta organização.")
        loja.codigo_filial = codigo
    if "unidade_matriz" in chaves:
        if payload.unidade_matriz:
            db.query(Estabelecimento).filter(
                Estabelecimento.organizacao_id == org.id,
                Estabelecimento.id != loja.id, Estabelecimento.unidade_matriz.is_(True)
            ).update({"unidade_matriz": False}, synchronize_session=False)
        loja.unidade_matriz = payload.unidade_matriz
    if "ativo" in chaves:
        loja.ativo = payload.ativo
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de filial duplicado.") from exc
    db.refresh(loja)
    return _filial_out(loja)


@router.get("/onboarding")
def onboarding_b2b(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    lojas = db.query(Estabelecimento).filter_by(organizacao_id=org.id).all()
    sku = db.query(Produto).filter_by(organizacao_id=org.id, tipo_produto="comercial").count()
    ofertas = db.query(Preco.id).join(Estabelecimento).filter(
        Estabelecimento.organizacao_id == org.id
    ).count()
    passos = [
        {"codigo": "cadastrar_filial", "titulo": "Cadastre sua primeira unidade", "concluido": bool(lojas)},
        {"codigo": "verificar_filial", "titulo": "Aguarde a verificação administrativa da unidade", "concluido": any(e.parceiro_verificado for e in lojas)},
        {"codigo": "cadastrar_sku", "titulo": "Cadastre um produto comercial", "concluido": sku > 0},
        {"codigo": "publicar_oferta", "titulo": "Publique uma oferta real", "concluido": ofertas > 0},
    ]
    return {"organizacao_id": org.id, "concluidos": sum(p["concluido"] for p in passos),
            "total": len(passos), "passos": passos,
            "contagens": {"filiais": len(lojas), "filiais_verificadas": sum(e.parceiro_verificado for e in lojas),
                          "produtos_comerciais": sku, "ofertas_registradas": ofertas}}


@router.get("/relatorios/comercial")
def relatorio_comercial(
    periodo_dias: int = Query(default=30, ge=1, le=365),
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    filiais = db.query(Estabelecimento).filter_by(organizacao_id=org.id).order_by(
        Estabelecimento.nome, Estabelecimento.id
    ).all()
    ids = [e.id for e in filiais]
    ofertas = {}
    interacoes = {}
    if ids:
        ofertas = dict(db.query(Preco.estabelecimento_id, func.count(Preco.id)).filter(
            Preco.estabelecimento_id.in_(ids)
        ).group_by(Preco.estabelecimento_id).all())
        interacoes = {
            (eid, tipo): quantidade
            for eid, tipo, quantidade in db.query(
                MetricaEstabelecimento.estabelecimento_id,
                MetricaEstabelecimento.tipo, func.count(MetricaEstabelecimento.id)
            ).filter(
                MetricaEstabelecimento.estabelecimento_id.in_(ids),
                MetricaEstabelecimento.criado_em >= agora() - timedelta(days=periodo_dias),
            ).group_by(MetricaEstabelecimento.estabelecimento_id,
                       MetricaEstabelecimento.tipo).all()
        }
    unidades = [
        {**_filial_out(e), "ofertas_registradas": ofertas.get(e.id, 0),
         "visualizacoes": interacoes.get((e.id, "visualizacao"), 0),
         "cliques_em_rota": interacoes.get((e.id, "clique"), 0)}
        for e in filiais
    ]
    return {
        "organizacao_id": org.id, "periodo_dias": periodo_dias,
        "metrica": "interacoes_de_descoberta_nao_transacionais",
        "vendas_confirmadas": None, "receita_confirmada": None,
        "unidades": unidades,
        "totais": {
            "filiais": len(filiais),
            "ofertas_registradas": sum(e["ofertas_registradas"] for e in unidades),
            "visualizacoes": sum(e["visualizacoes"] for e in unidades),
            "cliques_em_rota": sum(e["cliques_em_rota"] for e in unidades),
        },
    }


def _preco_decimal(valor: str | None, *, obrigatorio=False) -> Decimal | None:
    if valor is None or not valor.strip():
        if obrigatorio:
            raise ValueError("Preço obrigatório.")
        return None
    try:
        quantia = Decimal(valor.strip().replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Preço deve ser numérico.") from exc
    if not quantia.is_finite() or quantia <= 0 or quantia > 10000000:
        raise ValueError("Preço fora do intervalo válido.")
    if quantia.as_tuple().exponent < -2:
        raise ValueError("Preço deve conter no máximo duas casas decimais.")
    return quantia


@router.post("/importacoes/ofertas", status_code=201)
def importar_ofertas_csv(
    payload: ImportacaoOfertasCSV,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id, editar=True)
    # Serializa importações concorrentes e criações manuais na mesma organização.
    atual = db.query(Organizacao).filter_by(id=org.id, ativo=True).with_for_update().first()
    if not atual:
        raise HTTPException(status_code=404, detail="Organização desativada.")
    resumo_hash = hashlib.sha256(payload.csv_texto.encode("utf-8")).hexdigest()
    chave = payload.chave_idempotencia
    anterior = db.query(ImportacaoOfertas).filter_by(
        organizacao_id=org.id, chave_idempotencia=chave
    ).with_for_update().first()
    if anterior:
        if anterior.payload_hash != resumo_hash:
            raise HTTPException(status_code=409, detail="Chave de importação já utilizada com conteúdo diferente.")
        return {**anterior.resultado, "repetida": True}

    fonte = io.StringIO(payload.csv_texto.lstrip("\ufeff"))
    cabecalho = fonte.readline()
    if not cabecalho:
        raise HTTPException(status_code=422, detail="Arquivo CSV vazio.")
    delimitador = ";" if ";" in cabecalho else ","
    fonte.seek(0)
    leitor = csv.DictReader(fonte, delimiter=delimitador)
    campos = [c.strip() for c in (leitor.fieldnames or []) if c]
    if len(campos) != len(set(campos)) or not COLUNAS_OBRIGATORIAS.issubset(campos) or not set(campos).issubset(COLUNAS_PERMITIDAS):
        raise HTTPException(status_code=422, detail="Cabeçalho CSV inválido. Use estabelecimento_id;produto_id;preco;preco_original;estoque_status.")
    linhas = list(leitor)
    if not linhas or len(linhas) > MAX_LINHAS_CSV:
        raise HTTPException(status_code=422, detail=f"O CSV deve conter de 1 a {MAX_LINHAS_CSV} linhas de dados.")

    slug, _, _ = resolver_plano(db, org.id, bloqueio=True)
    restantes = max(0, LIMITES_PLANOS[slug]["ofertas"] - _contagem_atual(db, org.id, "ofertas", bloqueio=True))
    erros = []
    aceitos = []
    vistos = set()
    lojas_cache = {}
    produtos_cache = {}
    for n, linha in enumerate(linhas, start=2):
        try:
            if None in linha or any(v is None for v in linha.values()):
                raise ValueError("Linha CSV com número incorreto de colunas.")
            dados = {k.strip(): v.strip() for k, v in linha.items()}
            loja_id, produto_id = int(dados["estabelecimento_id"]), int(dados["produto_id"])
            if loja_id <= 0 or produto_id <= 0:
                raise ValueError("IDs de loja e produto devem ser positivos.")
            par = (loja_id, produto_id)
            if par in vistos:
                raise ValueError("Produto/filial duplicados neste lote.")
            vistos.add(par)
            preco = _preco_decimal(dados["preco"], obrigatorio=True)
            original = _preco_decimal(dados.get("preco_original"))
            estoque = dados.get("estoque_status") or "disponivel"
            if estoque not in ESTOQUES_VALIDOS:
                raise ValueError("Status de estoque inválido.")
            if loja_id not in lojas_cache:
                lojas_cache[loja_id] = db.query(Estabelecimento).filter_by(
                    id=loja_id, organizacao_id=org.id, ativo=True
                ).first()
            loja = lojas_cache[loja_id]
            if loja is None:
                raise ValueError("Filial não encontrada ou inativa nesta organização.")
            if produto_id not in produtos_cache:
                produtos_cache[produto_id] = db.query(Produto).filter_by(
                    id=produto_id, ativo=True
                ).first()
            produto = produtos_cache[produto_id]
            if produto is None or produto.organizacao_id not in (None, org.id):
                raise ValueError("Produto indisponível para esta organização.")
            if len(aceitos) >= restantes:
                raise ValueError("Limite de ofertas do plano atingido.")
            aceitos.append(Preco(
                estabelecimento_id=loja.id, produto_id=produto.id,
                preco=preco, preco_original=original, moeda="BRL",
                estoque_status=estoque, disponivel=estoque != "indisponivel",
                origem="importacao_csv_parceiro", fonte="painel-parceiro:csv",
                criado_por_usuario_id=usuario.id, coletado_em=agora(),
                data_atualizacao=agora(),
            ))
        except (ValueError, KeyError, TypeError) as exc:
            erros.append({"linha": n, "erro": str(exc)})

    db.add_all(aceitos)
    resultado = {
        "organizacao_id": org.id, "chave_idempotencia": chave, "linhas": len(linhas),
        "criadas": len(aceitos), "rejeitadas": len(erros), "erros": erros, "repetida": False,
    }
    lote = ImportacaoOfertas(
        organizacao_id=org.id, usuario_id=usuario.id,
        chave_idempotencia=chave, payload_hash=resumo_hash, resultado=resultado,
    )
    db.add(lote)
    db.commit()
    return resultado
