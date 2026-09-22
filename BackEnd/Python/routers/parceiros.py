from datetime import UTC, datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import get_db
from models import Estabelecimento, MetricaEstabelecimento, Preco, Produto, Usuario
from schemas.auth import UsuarioOut
from schemas.estabelecimento import EstabelecimentoOut, EstabelecimentoParceiroCreate, PrecoComparacaoItem, PrecoParceiroCreate
from schemas.produto import ProdutoComercialCreate, ProdutoOut
from services.auth import exigir_papeis, usuario_atual_com_csrf
from services.catalogo_produtos import slugificar
from routers.produtos import produto_out

router = APIRouter(prefix="/api/parceiro", tags=["parceiros"])


def _estab_out(e: Estabelecimento) -> EstabelecimentoOut:
    return EstabelecimentoOut.model_validate(e)


def _estabelecimento_do_parceiro(db: Session, estabelecimento_id: int, usuario: Usuario) -> Estabelecimento:
    e = db.get(Estabelecimento, estabelecimento_id)
    if not e or (usuario.papel != "admin" and e.usuario_responsavel_id != usuario.id):
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado para esta conta.")
    return e


@router.post("/ativar", response_model=UsuarioOut)
def ativar_perfil_parceiro(usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    if usuario.papel == "usuario":
        usuario.papel = "parceiro"
        db.commit(); db.refresh(usuario)
    return usuario


@router.get("/estabelecimentos", response_model=list[EstabelecimentoOut])
def meus_estabelecimentos(usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")), db: Session = Depends(get_db)):
    q = db.query(Estabelecimento)
    if usuario.papel != "admin": q = q.filter(Estabelecimento.usuario_responsavel_id == usuario.id)
    return [_estab_out(e) for e in q.order_by(Estabelecimento.nome).all()]


@router.post("/estabelecimentos", response_model=EstabelecimentoOut, status_code=201)
def criar_estabelecimento(payload: EstabelecimentoParceiroCreate, usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)), db: Session = Depends(get_db)):
    base = slugificar(payload.nome) or "estabelecimento"
    slug = base
    while db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first():
        slug = f"{base}-{secrets.token_hex(3)}"
    e = Estabelecimento(
        usuario_responsavel_id=usuario.id, slug=slug, parceiro_verificado=(usuario.papel == "admin"), ativo=True,
        **payload.model_dump(),
    )
    db.add(e); db.commit(); db.refresh(e)
    return _estab_out(e)


@router.put("/estabelecimentos/{estabelecimento_id}", response_model=EstabelecimentoOut)
def atualizar_estabelecimento(estabelecimento_id: int, payload: EstabelecimentoParceiroCreate, usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)), db: Session = Depends(get_db)):
    e = _estabelecimento_do_parceiro(db, estabelecimento_id, usuario)
    for k, v in payload.model_dump().items(): setattr(e, k, v)
    db.commit(); db.refresh(e)
    return _estab_out(e)


@router.post("/produtos", response_model=ProdutoOut, status_code=201)
def criar_produto_comercial(payload: ProdutoComercialCreate, usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)), db: Session = Depends(get_db)):
    pai = db.get(Produto, payload.produto_pai_id)
    if not pai or pai.tipo_produto != "generico":
        raise HTTPException(status_code=422, detail="Selecione um produto genérico válido como categoria comercial.")
    if payload.ean and db.query(Produto).filter(Produto.ean == payload.ean).first():
        raise HTTPException(status_code=409, detail="Já existe um produto com este EAN.")
    base = slugificar(f"{payload.marca}-{payload.nome}-{payload.quantidade_embalagem}-{payload.unidade_embalagem}")
    slug = base or f"produto-{secrets.token_hex(4)}"
    while db.query(Produto).filter(Produto.slug == slug).first(): slug = f"{base}-{secrets.token_hex(3)}"
    p = Produto(
        categoria_id=pai.categoria_id, produto_pai_id=pai.id, tipo_produto="comercial", slug=slug,
        nome=payload.nome, marca=payload.marca, variante=payload.variante, fabricante=payload.fabricante,
        ean=payload.ean, sku=payload.sku, unidade_consumo=pai.unidade_consumo,
        unidade_venda=payload.unidade_venda, venda_fracionada=False, incremento_venda=None,
        quantidade_embalagem=payload.quantidade_embalagem, unidade_embalagem=payload.unidade_embalagem,
        ativo=True, imagem_url=payload.imagem_url, descricao=payload.descricao,
    )
    db.add(p)
    try:
        db.commit(); db.refresh(p)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Produto comercial duplicado.")
    return produto_out(db, p)


@router.get("/produtos", response_model=list[ProdutoOut])
def listar_produtos_comerciais(usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")), db: Session = Depends(get_db)):
    return [produto_out(db, p) for p in db.query(Produto).filter(Produto.tipo_produto == "comercial").order_by(Produto.nome).all()]


@router.post("/precos", response_model=PrecoComparacaoItem, status_code=201)
def cadastrar_preco(payload: PrecoParceiroCreate, usuario: Usuario = Depends(exigir_papeis("parceiro", "admin", mutacao=True)), db: Session = Depends(get_db)):
    e = _estabelecimento_do_parceiro(db, payload.estabelecimento_id, usuario)
    p = db.get(Produto, payload.produto_id)
    if not p or not p.ativo:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    preco = Preco(
        produto_id=p.id, estabelecimento_id=e.id, criado_por_usuario_id=usuario.id,
        preco=payload.preco, preco_original=payload.preco_original, moeda="BRL",
        fonte=f"painel-parceiro:{usuario.id}", origem="manual_parceiro",
        estoque_status=payload.estoque_status, disponivel=payload.estoque_status != "indisponivel",
        inicio_validade=payload.inicio_validade, fim_validade=payload.fim_validade,
        coletado_em=datetime.now(UTC).replace(tzinfo=None), data_atualizacao=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(preco); db.commit(); db.refresh(preco)
    return PrecoComparacaoItem(
        preco_id=preco.id, produto_id=p.id, produto=p.nome, estabelecimento_id=e.id, estabelecimento=e.nome,
        preco=float(preco.preco), preco_original=float(preco.preco_original) if preco.preco_original is not None else None,
        unidade_venda=p.unidade_venda, coletado_em=preco.coletado_em.isoformat(), data_atualizacao=preco.data_atualizacao.isoformat(),
        inicio_validade=preco.inicio_validade.isoformat() if preco.inicio_validade else None,
        fim_validade=preco.fim_validade.isoformat() if preco.fim_validade else None,
        estoque_status=preco.estoque_status, fonte=preco.fonte, origem=preco.origem,
    )


@router.get("/dashboard")
def dashboard(usuario: Usuario = Depends(exigir_papeis("parceiro", "admin")), db: Session = Depends(get_db)):
    q = db.query(Estabelecimento)
    if usuario.papel != "admin": q = q.filter(Estabelecimento.usuario_responsavel_id == usuario.id)
    estabelecimentos = q.all(); ids = [e.id for e in estabelecimentos]
    precos = db.query(Preco).filter(Preco.estabelecimento_id.in_(ids)).count() if ids else 0
    visualizacoes = db.query(MetricaEstabelecimento).filter(
        MetricaEstabelecimento.estabelecimento_id.in_(ids), MetricaEstabelecimento.tipo == "visualizacao"
    ).count() if ids else 0
    cliques = db.query(MetricaEstabelecimento).filter(
        MetricaEstabelecimento.estabelecimento_id.in_(ids), MetricaEstabelecimento.tipo == "clique"
    ).count() if ids else 0
    return {
        "estabelecimentos": len(estabelecimentos), "estabelecimentos_verificados": sum(e.parceiro_verificado for e in estabelecimentos),
        "ofertas_cadastradas": precos, "visualizacoes": visualizacoes, "cliques": cliques,
        "mensagem_verificacao": "Ofertas de estabelecimentos não verificados ficam fora da recomendação pública até aprovação.",
    }


@router.post("/admin/estabelecimentos/{estabelecimento_id}/verificar", response_model=EstabelecimentoOut)
def verificar_estabelecimento(estabelecimento_id: int, usuario: Usuario = Depends(exigir_papeis("admin", mutacao=True)), db: Session = Depends(get_db)):
    e = db.get(Estabelecimento, estabelecimento_id)
    if not e: raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")
    e.parceiro_verificado = True; db.commit(); db.refresh(e)
    return _estab_out(e)
