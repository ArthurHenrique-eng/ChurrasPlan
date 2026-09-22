from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from sqlalchemy.orm import Session

from models import Estabelecimento, ListaCompras, Preco, Produto
from services.calculo_precos import listar_ofertas_atuais
from services.catalogo_produtos import ProdutoComercial, converter_produto


def distancia_km(lat1, lon1, lat2, lon2):
    if None in {lat1, lon1, lat2, lon2}: return None
    r = 6371.0088
    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*r*asin(sqrt(a))


def _produto_comercial(p: Produto) -> ProdutoComercial:
    return ProdutoComercial(
        id=p.id, slug=p.slug, nome=p.nome, categoria=p.categoria.tipo if p.categoria else "outro",
        unidade_consumo=p.unidade_consumo, unidade_venda=p.unidade_venda, venda_fracionada=p.venda_fracionada,
        incremento_venda=float(p.incremento_venda) if p.incremento_venda is not None else None,
        quantidade_embalagem=float(p.quantidade_embalagem) if p.quantidade_embalagem is not None else None,
        unidade_embalagem=p.unidade_embalagem,
    )


def _candidatos_produto(db: Session, produto_id: int) -> list[Produto]:
    p = db.get(Produto, produto_id)
    if not p: return []
    raiz = p.produto_pai_id or p.id
    candidatos = db.query(Produto).filter(
        Produto.ativo.is_(True), ((Produto.id == raiz) | (Produto.produto_pai_id == raiz))
    ).all()
    return candidatos


def _ofertas_item(db: Session, item) -> list[dict]:
    saida = []
    if not item.produto_id: return saida
    necessario = float(item.quantidade)
    for p in _candidatos_produto(db, item.produto_id):
        comercial = _produto_comercial(p)
        compra = converter_produto(comercial, necessario)
        qtd_cobrada = compra.compra if p.venda_fracionada else (compra.embalagens or 0)
        for preco in listar_ofertas_atuais(db, p.id, incluir_parceiro_nao_verificado=False):
            subtotal = round(float(preco.preco) * float(qtd_cobrada), 2)
            saida.append({
                "item_lista_id": item.id, "descricao": item.descricao, "produto_id": p.id,
                "produto_nome": p.nome, "estabelecimento_id": preco.estabelecimento_id,
                "estabelecimento_nome": preco.estabelecimento.nome, "quantidade_compra": float(compra.compra),
                "unidade_venda": p.unidade_venda, "preco_unitario": float(preco.preco), "subtotal": subtotal,
            })
    return saida


def otimizar_compra(db: Session, lista: ListaCompras, latitude: float | None = None, longitude: float | None = None, modo: str = "equilibrio") -> dict:
    ofertas_por_item = {item.id: _ofertas_item(db, item) for item in lista.itens}
    estabelecimentos_ids = {o["estabelecimento_id"] for ofertas in ofertas_por_item.values() for o in ofertas}
    cestas = []
    total_itens = len(lista.itens)
    for eid in estabelecimentos_ids:
        e = db.get(Estabelecimento, eid)
        itens = []
        for item in lista.itens:
            candidatos = [o for o in ofertas_por_item[item.id] if o["estabelecimento_id"] == eid]
            if candidatos: itens.append(min(candidatos, key=lambda o: o["subtotal"]))
        total = round(sum(i["subtotal"] for i in itens), 2)
        dist = distancia_km(latitude, longitude, e.latitude, e.longitude) if latitude is not None and longitude is not None else None
        cobertura = round(len(itens) / total_itens * 100, 1) if total_itens else 0
        cestas.append({
            "estabelecimento_id": eid, "estabelecimento_nome": e.nome, "total": total,
            "itens_encontrados": len(itens), "itens_total": total_itens, "cobertura_percentual": cobertura,
            "distancia_km": round(dist, 2) if dist is not None else None,
            "avaliacao": float(e.avaliacao) if e.avaliacao is not None else None,
            "quantidade_avaliacoes": e.quantidade_avaliacoes, "itens": itens,
        })
    completos = [c for c in cestas if c["itens_encontrados"] == total_itens]
    if cestas:
        max_total = max(c["total"] for c in cestas) or 1
        distancias = [c["distancia_km"] for c in cestas if c["distancia_km"] is not None]
        max_dist = max(distancias) if distancias else 1
        for c in cestas:
            # Menor é melhor: 55% preço, 30% distância, 15% avaliação ponderada pela quantidade de reviews.
            preco_n = c["total"] / max_total
            dist_n = (c["distancia_km"] / max_dist) if c["distancia_km"] is not None and max_dist else 0.5
            rating = c["avaliacao"] or 0
            confianca = min(1.0, ((c["quantidade_avaliacoes"] or 0) / 100))
            rating_n = 1 - ((rating / 5) * (0.5 + 0.5*confianca))
            cobertura_penalty = 1 - (c["cobertura_percentual"] / 100)
            c["score_equilibrio"] = round(.55*preco_n + .30*dist_n + .15*rating_n + cobertura_penalty, 4)
    if modo == "preco":
        cestas.sort(key=lambda c: (c["itens_encontrados"] != total_itens, c["total"]))
    elif modo == "distancia":
        cestas.sort(key=lambda c: (c["distancia_km"] is None, c["distancia_km"] or 999999, -c["cobertura_percentual"]))
    elif modo == "avaliacao":
        cestas.sort(key=lambda c: (-(c["avaliacao"] or 0), -(c["quantidade_avaliacoes"] or 0), -c["cobertura_percentual"]))
    else:
        cestas.sort(key=lambda c: c.get("score_equilibrio") or 999)

    otimizados = []
    for item in lista.itens:
        if ofertas_por_item[item.id]: otimizados.append(min(ofertas_por_item[item.id], key=lambda o: o["subtotal"]))
    total_otimizado = round(sum(i["subtotal"] for i in otimizados), 2) if len(otimizados) == total_itens and total_itens else None
    melhor_loja = min((c["total"] for c in completos), default=None)
    economia = round(melhor_loja - total_otimizado, 2) if melhor_loja is not None and total_otimizado is not None else None
    return {
        "cestas": cestas,
        "compra_otimizada": {
            "total": total_otimizado, "economia_vs_melhor_loja": economia,
            "estabelecimentos_usados": len({i["estabelecimento_id"] for i in otimizados}) if total_otimizado is not None else 0,
            "itens": otimizados,
        },
        "aviso": None if total_otimizado is not None else "Ainda não há ofertas verificadas para todos os itens da lista.",
    }
