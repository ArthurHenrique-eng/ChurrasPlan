"""Integração opcional com Geoapify Places e Address Autocomplete.

A chave usada pelo backend nunca é enviada ao navegador. Resultados externos
são usados somente em tempo de execução e não viram ofertas/preços próprios.
"""
from __future__ import annotations

import json
import logging
import hashlib
import math
import time
from collections import OrderedDict, deque
from threading import BoundedSemaphore, Lock
import urllib.error
import urllib.parse
import urllib.request

from config import settings

logger = logging.getLogger("churrasplan.geoapify")
_lock = Lock()
_concorrencia = BoundedSemaphore(4)
_cache = OrderedDict()
_falhas = 0
_aberto_ate = 0.0
_consumo = deque()


def _consultar(url: str, *, tile=False):
    global _falhas, _aberto_ate
    chave = hashlib.sha256(url.encode()).hexdigest()
    momento = time.monotonic()
    with _lock:
        entrada = _cache.get(chave)
        if entrada and entrada[0] > momento:
            _cache.move_to_end(chave)
            return entrada[1]
        while _consumo and _consumo[0] < momento - 60:
            _consumo.popleft()
        if momento < _aberto_ate or len(_consumo) >= 300:
            return None
        _consumo.append(momento)
    if not _concorrencia.acquire(blocking=False):
        return None
    try:
        for tentativa in range(2):
            req = urllib.request.Request(url, headers={"Accept": "image/png" if tile else "application/json", "User-Agent": "ChurrasPlan/Geoapify"})
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    corpo = resp.read(1024 * 1024 + 1)
                    if len(corpo) > 1024 * 1024:
                        raise ValueError("Resposta excede limite")
                    dado = (corpo, "image/png") if tile else json.loads(corpo)
                    if not tile and not isinstance(dado, dict):
                        raise ValueError("JSON inválido")
                with _lock:
                    _falhas = 0
                    _cache[chave] = (momento + (900 if tile else 120), dado)
                    while len(_cache) > 64:
                        _cache.popitem(last=False)
                return dado
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                codigo = getattr(exc, "code", None)
                logger.warning("geoapify_falha", extra={"evento": "geoapify_falha", "tipo_erro": type(exc).__name__})
                if codigo and codigo not in {429, 500, 502, 503, 504}:
                    break
                if tentativa == 0:
                    time.sleep(.1)
        with _lock:
            _falhas += 1
            if _falhas >= 3:
                _aberto_ate = time.monotonic() + 30
        return None
    finally:
        _concorrencia.release()


def _coordenadas_validas(lat, lon):
    try:
        return math.isfinite(float(lat)) and math.isfinite(float(lon)) and -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180
    except (TypeError, ValueError):
        return False

CATEGORIAS_COMPRAS_CHURRASCO = [
    "commercial.supermarket",
    "commercial.convenience",
    "commercial.discount_store",
    "commercial.marketplace",
    "commercial.food_and_drink.butcher",
]


def _get_json(url: str) -> dict:
    return _consultar(url) or {}



def buscar_tile_mapa(
    z: int,
    x: int,
    y: int,
    estilo: str = "osm-carto",
) -> tuple[bytes, str] | None:
    """Busca um tile raster pelo backend sem expor a chave Geoapify no browser."""
    if not settings.GEOAPIFY_ENABLED or not settings.GEOAPIFY_SERVER_API_KEY:
        return None

    estilos_permitidos = {
        "osm-carto",
        "osm-bright",
        "osm-bright-grey",
        "osm-bright-smooth",
        "positron",
        "positron-blue",
        "positron-red",
        "klokantech-basic",
        "osm-liberty",
        "toner",
        "toner-grey",
    }
    if estilo not in estilos_permitidos:
        estilo = "osm-carto"

    chave = urllib.parse.quote(settings.GEOAPIFY_SERVER_API_KEY, safe="")
    url = (
        f"https://maps.geoapify.com/v1/tile/{estilo}/{z}/{x}/{y}.png"
        f"?apiKey={chave}"
    )
    return _consultar(url, tile=True)

def buscar_proximos(
    latitude: float,
    longitude: float,
    raio_m: float = 15000,
    max_resultados: int = 20,
) -> list[dict]:
    if not settings.GEOAPIFY_ENABLED or not settings.GEOAPIFY_SERVER_API_KEY:
        return []
    if not _coordenadas_validas(latitude, longitude):
        return []

    raio = min(50000.0, max(100.0, float(raio_m)))
    params = urllib.parse.urlencode(
        {
            "categories": ",".join(CATEGORIAS_COMPRAS_CHURRASCO),
            "filter": f"circle:{longitude},{latitude},{raio:g}",
            "bias": f"proximity:{longitude},{latitude}",
            "limit": min(50, max(1, int(max_resultados))),
            "lang": "pt",
            "apiKey": settings.GEOAPIFY_SERVER_API_KEY,
        }
    )
    dados = _get_json(f"https://api.geoapify.com/v2/places?{params}")

    saida: list[dict] = []
    for feature in dados.get("features", []):
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            continue

        lon, lat = coords[0], coords[1]
        if not _coordenadas_validas(lat, lon):
            continue
        categorias = props.get("categories") or []
        tipo = next(
            (c for c in reversed(categorias) if c.startswith("commercial.")),
            categorias[-1] if categorias else None,
        )
        saida.append(
            {
                "provider_place_id": props.get("place_id"),
                "nome": props.get("name")
                or props.get("address_line1")
                or "Estabelecimento",
                "tipo": tipo,
                "endereco": props.get("formatted") or props.get("address_line2"),
                "latitude": lat,
                "longitude": lon,
                "avaliacao": None,
                "quantidade_avaliacoes": None,
            }
        )
    return saida


def autocomplete_enderecos(
    texto: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    limite: int = 6,
) -> list[dict]:
    if not settings.GEOAPIFY_ENABLED or not settings.GEOAPIFY_SERVER_API_KEY:
        return []

    params: dict[str, str | int] = {
        "text": texto,
        "format": "json",
        "lang": "pt",
        "filter": "countrycode:br",
        "limit": min(10, max(1, int(limite))),
        "apiKey": settings.GEOAPIFY_SERVER_API_KEY,
    }
    if latitude is not None and longitude is not None:
        params["bias"] = f"proximity:{longitude},{latitude}"

    dados = _get_json(
        "https://api.geoapify.com/v1/geocode/autocomplete?"
        + urllib.parse.urlencode(params)
    )

    saida: list[dict] = []
    for item in dados.get("results", []):
        lat = item.get("lat")
        lon = item.get("lon")
        if lat is None or lon is None:
            continue
        if not _coordenadas_validas(lat, lon):
            continue
        saida.append(
            {
                "place_id": item.get("place_id"),
                "label": item.get("formatted")
                or item.get("address_line1")
                or texto,
                "latitude": lat,
                "longitude": lon,
            }
        )
    return saida
