from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import CATALOGO_PRODUTOS_PADRAO
from database.connection import get_db
from models import Churrasco, Estabelecimento, ListaCompras, ListaComprasItem, Usuario
from schemas.lista_compras import ListaComprasItemOut, ListaComprasItemUpdate, ListaComprasOut
from services.auth import usuario_opcional, usuario_opcional_com_csrf
from services.precos_referencia import obter_preco_referencia

router = APIRouter(prefix="/api/lista-compras", tags=["lista-compras"])


NOME_CATALOGO_PARA_SLUG = {
    dados["nome"].strip().casefold(): slug
    for slug, dados in CATALOGO_PRODUTOS_PADRAO.items()
}


def _item_out(item: ListaComprasItem) -> ListaComprasItemOut:
    preco_unitario = float(item.preco_unitario) if item.preco_unitario is not None else None
    subtotal_estimado = float(item.subtotal_estimado) if item.subtotal_estimado is not None else None

    if preco_unitario is None:
        slug = item.produto.slug if item.produto is not None else NOME_CATALOGO_PARA_SLUG.get(item.descricao.strip().casefold())
        referencia = obter_preco_referencia(slug)
        if referencia is not None:
            preco_unitario = float(referencia)
            quantidade_cobrada = (
                float(item.quantidade_embalagens)
                if item.quantidade_embalagens is not None
                else float(item.quantidade)
            )
            subtotal_estimado = round(preco_unitario * quantidade_cobrada, 2)

    return ListaComprasItemOut(
        id=item.id,
        produto_id=item.produto_id,
        estabelecimento_compra_id=item.estabelecimento_compra_id,
        descricao=item.descricao,
        quantidade=float(item.quantidade),
        unidade=item.unidade,
        quantidade_embalagens=item.quantidade_embalagens,
        unidade_venda=item.unidade_venda,
        categoria=item.categoria,
        preco_unitario=preco_unitario,
        subtotal_estimado=subtotal_estimado,
        valor_pago_total=float(item.valor_pago_total) if item.valor_pago_total is not None else None,
        comprado=item.comprado,
        comprado_em=item.comprado_em,
    )


def _acesso(lista: ListaCompras, usuario: Usuario | None):
    dono = lista.churrasco.usuario_id
    if dono is not None and (not usuario or (usuario.id != dono and usuario.papel != "admin")):
        raise HTTPException(status_code=403, detail="Esta lista pertence a outra conta.")


def _out(lista: ListaCompras) -> ListaComprasOut:
    itens = [_item_out(i) for i in lista.itens]
    total = len(itens)
    estimados = [float(i.subtotal_estimado) for i in itens if i.subtotal_estimado is not None]
    itens_com_preco = len(estimados)
    itens_sem_preco = total - itens_com_preco
    total_estimado = round(sum(estimados), 2) if estimados else None
    estimativa_completa = total > 0 and itens_sem_preco == 0

    comprados = sum(1 for i in itens if i.comprado)
    itens_com_valor_pago = sum(1 for i in itens if i.comprado and i.valor_pago_total is not None)
    total_pago = round(sum(float(i.valor_pago_total) for i in itens if i.comprado and i.valor_pago_total is not None), 2)
    valor_pago_completo = total > 0 and comprados == total and itens_com_valor_pago == total
    economia = (
        round(total_estimado - total_pago, 2)
        if estimativa_completa and valor_pago_completo and total_estimado is not None
        else None
    )
    return ListaComprasOut(
        id=lista.id, churrasco_id=lista.churrasco_id, itens=itens,
        total_estimado=total_estimado, estimativa_completa=estimativa_completa,
        itens_com_preco=itens_com_preco, itens_sem_preco=itens_sem_preco,
        total_pago=total_pago, valor_pago_completo=valor_pago_completo,
        itens_com_valor_pago=itens_com_valor_pago, economia_real=economia,
        progresso_percentual=round((comprados / total * 100), 1) if total else 0,
        itens_comprados=comprados, itens_total=total,
    )


@router.get("/{churrasco_id}", response_model=ListaComprasOut)
def obter_lista_compras(churrasco_id: int, db: Session = Depends(get_db), usuario: Usuario | None = Depends(usuario_opcional)):
    lista = db.query(ListaCompras).filter(ListaCompras.churrasco_id == churrasco_id).first()
    if not lista:
        raise HTTPException(status_code=404, detail="Lista de compras não encontrada para este churrasco")
    _acesso(lista, usuario)
    return _out(lista)


@router.put("/item/{item_id}", response_model=ListaComprasItemOut)
def atualizar_item(item_id: int, payload: ListaComprasItemUpdate, db: Session = Depends(get_db), usuario: Usuario | None = Depends(usuario_opcional_com_csrf)):
    item = db.get(ListaComprasItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    _acesso(item.lista, usuario)
    if payload.estabelecimento_compra_id is not None and not db.get(Estabelecimento, payload.estabelecimento_compra_id):
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")
    item.comprado = payload.comprado
    item.valor_pago_total = payload.valor_pago_total if payload.comprado else None
    item.estabelecimento_compra_id = payload.estabelecimento_compra_id if payload.comprado else None
    item.comprado_em = datetime.now(UTC).replace(tzinfo=None) if payload.comprado else None
    db.commit(); db.refresh(item)
    return item
