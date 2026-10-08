"""Fase 4A: catálogo por lote e campanhas comerciais moderadas (sem billing)."""
from __future__ import annotations

import csv
import hashlib
import io
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import get_db
from models import (CampanhaComercial, CampanhaComercialItem, Estabelecimento,
                    ImportacaoCatalogo, Organizacao, Preco, Produto, Usuario)
from schemas.comercial_b2b import CampanhaCriar, CampanhaRevisao, CatalogoCSV
from services.auth import agora, exigir_papeis
from services.catalogo_produtos import slugificar
from services.entitlements import LIMITES_PLANOS, _contagem_atual, resolver_plano
from services.equipe_organizacao import exigir_gestao, registrar_acao
from services.organizacoes import selecionar_organizacao
from services.seguranca import registrar_auditoria

router = APIRouter(prefix="/api/parceiro", tags=["comercial-b2b"])
admin_router = APIRouter(prefix="/api/admin", tags=["moderacao-campanhas"])
public_router = APIRouter(prefix="/api/campanhas", tags=["campanhas-publicas"])

COLUNAS_CATALOGO = {"sku", "produto_pai_id", "nome", "marca", "unidade_venda",
                    "quantidade_embalagem", "unidade_embalagem"}
OPCIONAIS_CATALOGO = {"ean", "variante", "ativo"}
MAX_LINHAS = 200


def _org(db: Session, usuario: Usuario, oid: int | None, *, editar=False) -> Organizacao:
    org = selecionar_organizacao(db, usuario, oid, editar=editar)
    if org is None:
        raise HTTPException(status_code=409, detail="Selecione uma organização B2B.")
    return org


def _valor_decimal(valor: str) -> Decimal:
    try:
        n = Decimal(valor.replace(",", ".").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Quantidade da embalagem inválida.") from exc
    if not n.is_finite() or n <= 0 or n > 1_000_000 or n.as_tuple().exponent < -3:
        raise ValueError("Quantidade deve ser positiva, finita e ter até 3 casas decimais.")
    return n


def _codigo(valor: str, maximo: int, campo: str) -> str:
    x = (valor or "").strip()
    if not x or len(x) > maximo:
        raise ValueError(f"{campo} obrigatório (máximo {maximo} caracteres).")
    return x


def _upsert_csv(db: Session, org_id: int, linha: dict, vistos: set[str],
                eans: set[str], restantes: int) -> str:
    sku = _codigo(linha.get("sku"), 80, "SKU")
    if sku in vistos:
        raise ValueError("SKU repetido neste lote.")
    pid = int(linha["produto_pai_id"])
    pai = db.get(Produto, pid)
    if not pai or pai.tipo_produto != "generico" or not pai.ativo:
        raise ValueError("Produto genérico inválido.")
    nome = _codigo(linha.get("nome"), 120, "Nome")
    if len(nome) < 2:
        raise ValueError("Nome precisa de pelo menos 2 caracteres.")
    marca = _codigo(linha.get("marca"), 100, "Marca")
    unidade_venda = _codigo(linha.get("unidade_venda"), 30, "Unidade de venda")
    unidade_embalagem = _codigo(linha.get("unidade_embalagem"), 30, "Unidade de embalagem")
    quantidade = _valor_decimal(linha["quantidade_embalagem"])
    variante = (linha.get("variante") or "").strip() or None
    if variante and len(variante) > 120:
        raise ValueError("Variante muito longa.")
    ean = (linha.get("ean") or "").strip() or None
    if ean and (len(ean) < 8 or len(ean) > 32 or not ean.isdigit()):
        raise ValueError("EAN precisa ter de 8 a 32 dígitos.")
    if ean and ean in eans:
        raise ValueError("EAN repetido neste lote.")
    ativo = (linha.get("ativo") or "true").strip().lower()
    if ativo not in {"true", "false", "1", "0", "sim", "nao"}:
        raise ValueError("Ativo deve ser true/false, 1/0 ou sim/nao.")
    ativo = ativo in {"true", "1", "sim"}
    encontrados = db.query(Produto).filter_by(
        organizacao_id=org_id, tipo_produto="comercial", sku=sku
    ).limit(2).all()
    if len(encontrados) > 1:
        raise ValueError("SKU duplicado preexistente; saneie o cadastro manual.")
    produto = encontrados[0] if encontrados else None
    if produto and produto.produto_pai_id != pai.id:
        raise ValueError("Alteração do produto genérico de um SKU existente não é permitida.")
    if not produto and restantes <= 0:
        raise ValueError("Cota de produtos comerciais do plano atingida.")
    if ean:
        terceiro = db.query(Produto.id).filter(
            Produto.ean == ean,
            Produto.id != (produto.id if produto else -1),
        ).first()
        if terceiro:
            raise ValueError("EAN já cadastrado em outro produto.")
    if produto is None:
        base = slugificar(f"{marca}-{nome}-{sku}")[:110] or "sku"
        slug = f"{base}-{secrets.token_hex(6)}"
        produto = Produto(organizacao_id=org_id, tipo_produto="comercial",
                          slug=slug, categoria_id=pai.categoria_id,
                          produto_pai_id=pai.id, unidade_consumo=pai.unidade_consumo,
                          venda_fracionada=False, incremento_venda=None)
        db.add(produto)
        resultado = "criado"
    else:
        resultado = "atualizado"
    produto.nome, produto.marca, produto.variante = nome, marca, variante
    produto.sku, produto.ean, produto.ativo = sku, ean, ativo
    produto.unidade_venda = unidade_venda
    produto.quantidade_embalagem, produto.unidade_embalagem = quantidade, unidade_embalagem
    db.flush()
    vistos.add(sku)
    if ean:
        eans.add(ean)
    return resultado


@router.post("/importacoes/catalogo", status_code=201)
def importar_catalogo(
    payload: CatalogoCSV,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id, editar=True)
    # O lock do tenant serializa lotes e preserva o limite mesmo com escritores simultâneos.
    db.query(Organizacao).filter_by(id=org.id, ativo=True).with_for_update().one()
    hash_arquivo = hashlib.sha256(payload.csv_texto.encode("utf-8")).hexdigest()
    anterior = db.query(ImportacaoCatalogo).filter_by(
        organizacao_id=org.id, chave_idempotencia=payload.chave_idempotencia
    ).with_for_update().first()
    if anterior:
        if anterior.payload_hash != hash_arquivo:
            raise HTTPException(status_code=409, detail="Chave já utilizada com CSV diferente.")
        return {**anterior.resultado, "repetida": True}
    stream = io.StringIO(payload.csv_texto.lstrip("\ufeff"))
    primeiro = stream.readline()
    stream.seek(0)
    leitor = csv.DictReader(stream, delimiter=";" if ";" in primeiro else ",")
    campos = leitor.fieldnames or []
    if len(campos) != len(set(campos)) or not COLUNAS_CATALOGO.issubset(campos) or not set(campos).issubset(COLUNAS_CATALOGO | OPCIONAIS_CATALOGO):
        raise HTTPException(status_code=422, detail="Cabeçalho CSV comercial inválido.")
    linhas = list(leitor)
    if not 1 <= len(linhas) <= MAX_LINHAS:
        raise HTTPException(status_code=422, detail="CSV deve conter de 1 a 200 linhas.")
    plano, _, _ = resolver_plano(db, org.id, bloqueio=True)
    restante = max(0, LIMITES_PLANOS[plano]["produtos_comerciais"] -
                   _contagem_atual(db, org.id, "produtos_comerciais", bloqueio=True))
    vistos, eans, erros = set(), set(), []
    criados = atualizados = 0
    for n, dados in enumerate(linhas, start=2):
        try:
            if None in dados or any(valor is None for valor in dados.values()):
                raise ValueError("Número de colunas inválido.")
            with db.begin_nested():
                efeito = _upsert_csv(db, org.id, dados, vistos, eans, restante)
            if efeito == "criado":
                criados += 1
                restante -= 1
            else:
                atualizados += 1
        except (ValueError, TypeError, KeyError, IntegrityError) as exc:
            erros.append({"linha": n, "erro": "Conflito de integridade." if isinstance(exc, IntegrityError) else str(exc)})
    resultado = {"organizacao_id": org.id, "linhas": len(linhas), "criados": criados,
                 "atualizados": atualizados, "rejeitados": len(erros),
                 "erros": erros, "repetida": False,
                 "chave_idempotencia": payload.chave_idempotencia}
    db.add(ImportacaoCatalogo(organizacao_id=org.id, usuario_id=usuario.id,
            chave_idempotencia=payload.chave_idempotencia,
            payload_hash=hash_arquivo, resultado=resultado))
    db.commit()
    return resultado


def _campanha_out(c: CampanhaComercial, db: Session, *, publica=False) -> dict:
    n = agora()
    itens = []
    for rel in c.itens:
        p = rel.preco
        loja = p.estabelecimento
        produto = p.produto
        valida = (loja.ativo and loja.parceiro_verificado and produto.ativo
                  and p.disponivel and p.estoque_status != "indisponivel"
                  and (p.inicio_validade is None or p.inicio_validade <= n)
                  and (p.fim_validade is None or p.fim_validade >= n))
        if not publica or valida:
            itens.append({"preco_id": p.id, "estabelecimento_id": loja.id,
                          "estabelecimento": loja.nome, "produto_id": produto.id,
                          "produto": produto.nome, "preco": float(p.preco),
                          "preco_original": float(p.preco_original) if p.preco_original is not None else None})
    return {"id": c.id, "organizacao_id": c.organizacao_id, "codigo": c.codigo,
            "nome": c.nome, "descricao": c.descricao,
            "inicio_em": c.inicio_em.isoformat(), "fim_em": c.fim_em.isoformat(),
            "status": c.status, "ativa_agora": c.status == "aprovada" and c.inicio_em <= n < c.fim_em,
            "motivo_revisao": None if publica else c.motivo_revisao, "itens": itens}


def _verificar_ofertas(db: Session, org: Organizacao, ids: list[int], *, exigir_verificacao=False):
    precos = db.query(Preco).join(Estabelecimento).filter(
        Preco.id.in_(ids), Estabelecimento.organizacao_id == org.id
    ).all()
    if len(precos) != len(ids):
        raise HTTPException(status_code=404, detail="Uma ou mais ofertas não pertencem à organização.")
    for p in precos:
        if p.produto.organizacao_id not in (None, org.id):
            raise HTTPException(status_code=404, detail="Produto de outra organização.")
        if exigir_verificacao and (
            not p.estabelecimento.ativo or not p.estabelecimento.parceiro_verificado
            or not p.produto.ativo or not p.disponivel or p.estoque_status == "indisponivel"
        ):
            raise HTTPException(status_code=409, detail="Campanha exige loja verificada, produto ativo e estoque disponível.")
    return precos


def _alterar_campos(db: Session, campanha: CampanhaComercial, payload: CampanhaCriar, org: Organizacao):
    precos = _verificar_ofertas(db, org, payload.preco_ids)
    campanha.codigo, campanha.nome = payload.codigo.upper(), payload.nome
    campanha.descricao = payload.descricao
    campanha.inicio_em, campanha.fim_em = payload.inicio_em, payload.fim_em
    campanha.itens.clear()
    db.flush()
    for p in precos:
        campanha.itens.append(CampanhaComercialItem(preco_id=p.id))


@router.get("/ofertas/campanhas")
def ofertas_elegiveis(
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    """Seleção de ofertas internas, não um catálogo público de promoções."""
    org = _org(db, usuario, organizacao_id)
    ofertas = db.query(Preco).join(Estabelecimento).filter(
        Estabelecimento.organizacao_id == org.id,
        Estabelecimento.ativo.is_(True),
        Preco.disponivel.is_(True),
    ).order_by(Preco.id.desc()).limit(200).all()
    return [{"id": p.id, "produto": p.produto.nome, "estabelecimento": p.estabelecimento.nome,
             "preco": float(p.preco), "verificada": p.estabelecimento.parceiro_verificado}
            for p in ofertas if p.produto.organizacao_id in (None, org.id) and p.produto.ativo]


@router.get("/campanhas")
def listar_campanhas(usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")),
                    db: Session = Depends(get_db),
                    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID")):
    org = _org(db, usuario, organizacao_id)
    campanhas = db.query(CampanhaComercial).filter_by(organizacao_id=org.id).order_by(
        CampanhaComercial.id.desc()).limit(200).all()
    return [_campanha_out(c, db) for c in campanhas]


@router.post("/campanhas", status_code=201)
def criar_campanha(
    payload: CampanhaCriar,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    exigir_gestao(db, usuario, org.id)
    campanha = CampanhaComercial(organizacao_id=org.id, criado_por_usuario_id=usuario.id)
    db.add(campanha)
    _alterar_campos(db, campanha, payload, org)
    registrar_acao(db, org.id, usuario.id, "campanha_criada",
                   detalhes={"codigo": campanha.codigo, "ofertas": len(payload.preco_ids)})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de campanha já utilizado nesta organização.") from exc
    return _campanha_out(campanha, db)


@router.put("/campanhas/{campanha_id}")
def atualizar_campanha(
    campanha_id: int, payload: CampanhaCriar,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    exigir_gestao(db, usuario, org.id)
    c = db.query(CampanhaComercial).filter_by(
        id=campanha_id, organizacao_id=org.id
    ).with_for_update().first()
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    if c.status not in ("rascunho", "rejeitada"):
        raise HTTPException(status_code=409, detail="Somente campanhas em rascunho ou rejeitadas podem ser editadas.")
    _alterar_campos(db, c, payload, org)
    c.status, c.motivo_revisao = "rascunho", None
    registrar_acao(db, org.id, usuario.id, "campanha_editada", detalhes={"campanha_id": c.id})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de campanha duplicado.") from exc
    return _campanha_out(c, db)


@router.post("/campanhas/{campanha_id}/enviar")
def enviar_revisao(
    campanha_id: int,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    exigir_gestao(db, usuario, org.id)
    c = db.query(CampanhaComercial).filter_by(
        id=campanha_id, organizacao_id=org.id
    ).with_for_update().first()
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    if c.status != "rascunho" or c.fim_em <= agora():
        raise HTTPException(status_code=409, detail="Campanha fora do rascunho ou com vigência expirada.")
    _verificar_ofertas(db, org, [i.preco_id for i in c.itens])
    if not c.itens:
        raise HTTPException(status_code=422, detail="Campanha sem ofertas.")
    c.status = "em_revisao"
    registrar_acao(db, org.id, usuario.id, "campanha_enviada", detalhes={"campanha_id": c.id})
    db.commit()
    return _campanha_out(c, db)


@router.post("/campanhas/{campanha_id}/cancelar")
def cancelar_campanha(
    campanha_id: int,
    usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)),
    db: Session = Depends(get_db),
    organizacao_id: int | None = Header(default=None, alias="X-Organizacao-ID"),
):
    org = _org(db, usuario, organizacao_id)
    exigir_gestao(db, usuario, org.id)
    c = db.query(CampanhaComercial).filter_by(
        id=campanha_id, organizacao_id=org.id
    ).with_for_update().first()
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    if c.status == "cancelada":
        raise HTTPException(status_code=409, detail="Campanha já cancelada.")
    c.status = "cancelada"
    registrar_acao(db, org.id, usuario.id, "campanha_cancelada", detalhes={"campanha_id": c.id})
    db.commit()
    return _campanha_out(c, db)


@admin_router.get("/campanhas/pendentes")
def campanhas_pendentes(
    admin: Usuario = Depends(exigir_papeis("admin")),
    db: Session = Depends(get_db),
):
    campanhas = db.query(CampanhaComercial).filter_by(status="em_revisao").order_by(
        CampanhaComercial.id).limit(200).all()
    return [_campanha_out(c, db) for c in campanhas]


@admin_router.post("/campanhas/{campanha_id}/revisar")
def revisar_campanha(
    campanha_id: int, payload: CampanhaRevisao,
    admin: Usuario = Depends(exigir_papeis("admin", mutacao=True)),
    db: Session = Depends(get_db),
):
    # A mesma linha de organização é serializada por aprovação e importações.
    registro = db.get(CampanhaComercial, campanha_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    org = db.query(Organizacao).filter_by(id=registro.organizacao_id, ativo=True).with_for_update().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização inativa.")
    c = db.query(CampanhaComercial).filter_by(id=campanha_id, organizacao_id=org.id).with_for_update().one()
    if c.status != "em_revisao":
        raise HTTPException(status_code=409, detail="Campanha não está pendente de revisão.")
    if payload.aprovar:
        if c.fim_em <= agora() or not c.itens:
            raise HTTPException(status_code=409, detail="Campanha sem ofertas ou expirada.")
        precos = _verificar_ofertas(db, org, [i.preco_id for i in c.itens], exigir_verificacao=True)
        for p in precos:
            if ((p.inicio_validade is not None and p.inicio_validade > c.inicio_em)
                    or (p.fim_validade is not None and p.fim_validade < c.fim_em)):
                raise HTTPException(status_code=409, detail="Vigência da oferta não cobre a campanha.")
    c.status = "aprovada" if payload.aprovar else "rejeitada"
    c.revisado_por_usuario_id, c.revisado_em = admin.id, agora()
    c.motivo_revisao = None if payload.aprovar else payload.motivo.strip()
    registrar_auditoria(db, admin, acao="campanha_revisada", entidade="campanha",
                       entidade_id=c.id, detalhes={"organizacao_id": org.id,
                       "status": c.status, "motivo": c.motivo_revisao})
    db.commit()
    return _campanha_out(c, db)


@public_router.get("/ativas")
def campanhas_ativas(db: Session = Depends(get_db)):
    """Somente ofertas verificadas e vigentes; nunca promove oferta não moderada."""
    momento = agora()
    campanhas = db.query(CampanhaComercial).join(Organizacao).filter(
        CampanhaComercial.status == "aprovada",
        CampanhaComercial.inicio_em <= momento,
        CampanhaComercial.fim_em > momento,
        Organizacao.ativo.is_(True),
    ).order_by(CampanhaComercial.id.desc()).limit(100).all()
    return [res for c in campanhas if (res := _campanha_out(c, db, publica=True))["itens"]]
