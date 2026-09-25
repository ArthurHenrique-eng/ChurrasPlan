from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from models import Produto
from schemas.produto import ProdutoOut
from services.calculo_precos import obter_resumo_preco

router = APIRouter(prefix="/api/produtos", tags=["produtos"])


def produto_out(db: Session, p: Produto) -> ProdutoOut:
    resumo = obter_resumo_preco(db, p.id)
    return ProdutoOut(
        id=p.id, produto_pai_id=p.produto_pai_id, tipo_produto=p.tipo_produto,
        slug=p.slug, nome=p.nome, categoria_id=p.categoria_id,
        categoria_nome=p.categoria.nome if p.categoria else None,
        categoria_tipo=p.categoria.tipo if p.categoria else None,
        marca=p.marca, variante=p.variante, fabricante=p.fabricante, ean=p.ean, sku=p.sku,
        unidade_consumo=p.unidade_consumo, unidade_venda=p.unidade_venda,
        venda_fracionada=p.venda_fracionada,
        incremento_venda=float(p.incremento_venda) if p.incremento_venda is not None else None,
        quantidade_embalagem=float(p.quantidade_embalagem) if p.quantidade_embalagem is not None else None,
        unidade_embalagem=p.unidade_embalagem, ativo=p.ativo,
        imagem_url=p.imagem_url, descricao=p.descricao,
        preco_medio_historico=resumo.preco_medio_historico if resumo else None,
        preco_minimo_atual=resumo.preco_minimo_atual if resumo else None,
    )


@router.get("", response_model=list[ProdutoOut])
def listar_produtos(
    categoria_id: int | None = None, apenas_ativos: bool = True,
    tipo_produto: str | None = None, produto_pai_id: int | None = None,
    busca: str | None = None, db: Session = Depends(get_db),
):
    query = db.query(Produto)
    if categoria_id is not None: query = query.filter(Produto.categoria_id == categoria_id)
    if apenas_ativos: query = query.filter(Produto.ativo.is_(True))
    if tipo_produto is not None: query = query.filter(Produto.tipo_produto == tipo_produto)
    if produto_pai_id is not None: query = query.filter(Produto.produto_pai_id == produto_pai_id)
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter((Produto.nome.ilike(termo)) | (Produto.marca.ilike(termo)) | (Produto.ean.ilike(termo)))
    return [produto_out(db, p) for p in query.order_by(Produto.nome.asc()).all()]


@router.get("/{produto_id}", response_model=ProdutoOut)
def obter_produto(produto_id: int, db: Session = Depends(get_db)):
    p = db.get(Produto, produto_id)
    if not p: raise HTTPException(status_code=404, detail="Produto não encontrado")
    return produto_out(db, p)
