"""Integração opcional com Places API (New).

A consulta é feita somente quando GOOGLE_PLACES_ENABLED=true e a chave de
servidor está configurada. Conteúdo retornado pelo Google não é persistido por
este serviço; o cadastro próprio pode guardar apenas o Place ID quando houver
vínculo explícito com um estabelecimento do ChurrasPlan.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from config import settings

logger = logging.getLogger(__name__)

TIPOS_COMPRAS_CHURRASCO = [
    "supermarket",
    "grocery_store",
    "butcher_shop",
    "market",
    "discount_supermarket",
    "hypermarket",
    "warehouse_store",
]


def buscar_proximos(
    latitude: float,
    longitude: float,
    raio_m: float = 15000,
    max_resultados: int = 20,
) -> list[dict]:
    if not settings.GOOGLE_PLACES_ENABLED or not settings.GOOGLE_PLACES_API_KEY:
        return []

    corpo = {
        "includedTypes": TIPOS_COMPRAS_CHURRASCO,
        "maxResultCount": min(20, max(1, int(max_resultados))),
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": min(50000.0, max(100.0, float(raio_m))),
            }
        },
        "rankPreference": "DISTANCE",
        "languageCode": "pt-BR",
        "regionCode": "BR",
    }

    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchNearby",
        data=json.dumps(corpo).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.primaryType,"
                "places.formattedAddress,places.location,places.rating,"
                "places.userRatingCount,places.googleMapsUri,places.businessStatus"
            ),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("Places API respondeu HTTP %s", exc.code)
        return []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Falha temporária ao consultar Places API: %s", exc.__class__.__name__)
        return []

    saida: list[dict] = []
    for p in dados.get("places", []):
        if p.get("businessStatus") == "CLOSED_PERMANENTLY":
            continue
        loc = p.get("location") or {}
        if "latitude" not in loc or "longitude" not in loc:
            continue
        saida.append(
            {
                "google_place_id": p.get("id"),
                "nome": (p.get("displayName") or {}).get("text") or "Estabelecimento",
                "tipo": p.get("primaryType"),
                "endereco": p.get("formattedAddress"),
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "avaliacao": p.get("rating"),
                "quantidade_avaliacoes": p.get("userRatingCount"),
                "google_maps_uri": p.get("googleMapsUri"),
            }
        )
    return saida
