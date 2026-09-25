"""Integração opcional com Geoapify Places e Address Autocomplete.

A chave usada pelo backend nunca é enviada ao navegador. Resultados externos
são usados somente em tempo de execução e não viram ofertas/preços próprios.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from config import settings

logger = logging.getLogger(__name__)

CATEGORIAS_COMPRAS_CHURRASCO = [
    "commercial.supermarket",
    "commercial.convenience",
    "commercial.discount_store",
    "commercial.marketplace",
    "commercial.food_and_drink.butcher",
]


def _get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "ChurrasPlan/Geoapify",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("Geoapify respondeu HTTP %s", exc.code)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Falha temporária ao consultar Geoapify: %s",
            exc.__class__.__name__,
        )
    return {}



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
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "image/png",
            "User-Agent": "ChurrasPlan/Geoapify",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read(), resp.headers.get_content_type() or "image/png"
    except urllib.error.HTTPError as exc:
        logger.warning("Geoapify Map Tiles respondeu HTTP %s", exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "Falha temporária ao consultar Geoapify Map Tiles: %s",
            exc.__class__.__name__,
        )
    return None

def buscar_proximos(
    latitude: float,
    longitude: float,
    raio_m: float = 15000,
    max_resultados: int = 20,
) -> list[dict]:
    if not settings.GEOAPIFY_ENABLED or not settings.GEOAPIFY_SERVER_API_KEY:
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
