from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from models import Churrasco, Estabelecimento, ListaCompras, MetricaEstabelecimento, Usuario
from schemas.otimizacao import (
    EnderecoAutocompleteOut, EstabelecimentoProximoOut, InteracaoEstabelecimentosIn,
    LocalizacaoIn, OtimizacaoConsultaIn, OtimizacaoOut,
)
from services.auth import usuario_atual, usuario_atual_com_csrf
from services.geoapify import autocomplete_enderecos, buscar_proximos
from services.otimizacao import distancia_km, otimizar_compra

router = APIRouter(prefix="/api/onde-comprar", tags=["onde-comprar"])


def _churrasco_usuario(db: Session, churrasco_id: int, usuario: Usuario):
    c = db.get(Churrasco, churrasco_id)
    if not c or (c.usuario_id != usuario.id and usuario.papel != "admin"):
        raise HTTPException(status_code=404, detail="Churrasco não encontrado na sua conta.")
    return c


@router.get("/config")
def config_mapa(usuario: Usuario = Depends(usuario_atual)):
    # A chave de mapa é necessariamente visível no navegador para carregar
    # tiles Geoapify e deve ser restrita por HTTP referrer/origin. A chave de
    # servidor usada por Places/Autocomplete nunca é retornada ao frontend.
    return {
        "geoapify_map_disponivel": bool(settings.GEOAPIFY_ENABLED and settings.GEOAPIFY_MAP_API_KEY),
        "geoapify_places_disponivel": bool(settings.GEOAPIFY_ENABLED and settings.GEOAPIFY_SERVER_API_KEY),
        "geoapify_map_api_key": settings.GEOAPIFY_MAP_API_KEY or None,
    }


@router.get("/autocomplete", response_model=list[EnderecoAutocompleteOut])
def autocomplete_local(
    texto: str = Query(min_length=3, max_length=120),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    limite: int = Query(default=6, ge=1, le=10),
    usuario: Usuario = Depends(usuario_atual),
):
    return autocomplete_enderecos(
        texto.strip(),
        latitude=latitude,
        longitude=longitude,
        limite=limite,
    )


def _listar_proximos(latitude: float, longitude: float, raio_km: float, db: Session):
    saida = []
    for e in db.query(Estabelecimento).filter(Estabelecimento.ativo.is_(True)).all():
        if e.latitude is None or e.longitude is None:
            continue
        d = distancia_km(latitude, longitude, e.latitude, e.longitude)
        if d is not None and d <= raio_km:
            saida.append(EstabelecimentoProximoOut(
                fonte="churrasplan", estabelecimento_id=e.id, provider_place_id=None, nome=e.nome, tipo=e.tipo,
                endereco=e.endereco, latitude=e.latitude, longitude=e.longitude, distancia_km=round(d, 2),
                avaliacao=float(e.avaliacao) if e.avaliacao is not None else None, quantidade_avaliacoes=e.quantidade_avaliacoes,
                parceiro_verificado=e.parceiro_verificado,
            ))
    for p in buscar_proximos(latitude, longitude, raio_km * 1000):
        d = distancia_km(latitude, longitude, p["latitude"], p["longitude"])
        saida.append(EstabelecimentoProximoOut(
            fonte="geoapify", nome=p["nome"], tipo=p.get("tipo"), endereco=p.get("endereco"),
            latitude=p["latitude"], longitude=p["longitude"], distancia_km=round(d, 2) if d is not None else None,
            avaliacao=p.get("avaliacao"), quantidade_avaliacoes=p.get("quantidade_avaliacoes"),
            provider_place_id=p.get("provider_place_id"), provider_url=None, parceiro_verificado=False,
        ))
    return sorted(saida, key=lambda x: x.distancia_km if x.distancia_km is not None else 999999)


@router.post("/proximos", response_model=list[EstabelecimentoProximoOut])
def estabelecimentos_proximos(
    payload: LocalizacaoIn, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
):
    # POST evita colocar coordenadas pessoais na query string/access logs.
    return _listar_proximos(payload.latitude, payload.longitude, payload.raio_km, db)


@router.get("/proximos", response_model=list[EstabelecimentoProximoOut], deprecated=True)
def estabelecimentos_proximos_compat(
    latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180),
    raio_km: float = Query(default=15, ge=1, le=50), usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
):
    return _listar_proximos(latitude, longitude, raio_km, db)


@router.get("/churrasco/{churrasco_id}", response_model=OtimizacaoOut)
def comparar_churrasco(
    churrasco_id: int, modo: str = Query(default="equilibrio", pattern="^(preco|distancia|avaliacao|equilibrio)$"),
    latitude: float | None = Query(default=None, ge=-90, le=90), longitude: float | None = Query(default=None, ge=-180, le=180),
    usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
):
    c = _churrasco_usuario(db, churrasco_id, usuario)
    lista = c.lista_compras
    if not lista: raise HTTPException(status_code=404, detail="Lista de compras não encontrada.")
    dados = otimizar_compra(db, lista, latitude, longitude, modo)
    return OtimizacaoOut(churrasco_id=c.id, modo=modo, **dados)


@router.post("/churrasco/{churrasco_id}", response_model=OtimizacaoOut)
def comparar_churrasco_post(
    churrasco_id: int, payload: OtimizacaoConsultaIn,
    usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
):
    # Leitura via POST para não expor localização na URL.
    c = _churrasco_usuario(db, churrasco_id, usuario)
    lista = c.lista_compras
    if not lista:
        raise HTTPException(status_code=404, detail="Lista de compras não encontrada.")
    dados = otimizar_compra(db, lista, payload.latitude, payload.longitude, payload.modo)
    return OtimizacaoOut(churrasco_id=c.id, modo=payload.modo, **dados)


@router.post("/interacoes", status_code=204)
def registrar_interacoes(
    payload: InteracaoEstabelecimentosIn,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    tipo = (payload.tipo or "").strip().lower()
    if tipo not in {"visualizacao", "clique"}:
        raise HTTPException(status_code=422, detail="Tipo de interação inválido.")
    ids = list(dict.fromkeys(payload.estabelecimento_ids or []))
    if not ids or len(ids) > 50:
        raise HTTPException(status_code=422, detail="Informe entre 1 e 50 estabelecimentos.")
    contexto = (payload.contexto or "onde_comprar").strip()[:40] or "onde_comprar"
    if payload.churrasco_id is not None:
        _churrasco_usuario(db, payload.churrasco_id, usuario)
    existentes = {row[0] for row in db.query(Estabelecimento.id).filter(Estabelecimento.id.in_(ids), Estabelecimento.ativo.is_(True)).all()}
    for estabelecimento_id in ids:
        if estabelecimento_id in existentes:
            db.add(MetricaEstabelecimento(
                estabelecimento_id=estabelecimento_id,
                tipo=tipo,
                contexto=contexto,
            ))
    db.commit()
    return None
