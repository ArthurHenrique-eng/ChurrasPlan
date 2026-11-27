"""Integração opcional com o Neon Realtime (consultas ao vivo).

A API continua dona da autorização: o router confere a sessão e se o usuário
pode ver os dados e só então pede à Neon Function `selarrt` que sele uma
consulta da lista fechada (veja neon/functions/selarrt-handler.ts). O pedido
é assinado com HMAC-SHA256 do corpo e do horário, com o segredo compartilhado
REALTIME_SELO_SEGREDO. O navegador recebe só a consulta selada (cifrada e
válida por cerca de 60 s) e a URL WSS do Realtime.

Sem as três variáveis configuradas o recurso fica desligado e a tela usa a
lista carregada pela API, como antes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

import httpx

from config import settings

logger = logging.getLogger("churrasplan.realtime")

TIMEOUT_SEGUNDOS = 5.0
CABECALHO_TIMESTAMP = "x-churrasplan-ts"
CABECALHO_ASSINATURA = "x-churrasplan-assinatura"


class RealtimeIndisponivel(Exception):
    """O Realtime não está configurado ou a Function não respondeu como esperado."""


def realtime_configurado() -> bool:
    return bool(settings.NEON_REALTIME_URL and settings.NEON_SELARRT_URL and settings.REALTIME_SELO_SEGREDO)


def assinar(segredo: str, timestamp: str, corpo: str) -> str:
    return hmac.new(segredo.encode("utf-8"), f"{timestamp}.{corpo}".encode("utf-8"), hashlib.sha256).hexdigest()


def _validar_selada(dados: object) -> dict:
    if not isinstance(dados, dict):
        raise RealtimeIndisponivel("resposta não é um objeto")
    capability = dados.get("capability")
    impressao = dados.get("queryFingerprint")
    expira = dados.get("expiresAt")
    if not isinstance(capability, str) or not capability or len(capability) > 65536:
        raise RealtimeIndisponivel("capability ausente")
    if not isinstance(impressao, str) or not impressao:
        raise RealtimeIndisponivel("queryFingerprint ausente")
    if isinstance(expira, bool) or not isinstance(expira, int) or expira <= int(time.time() * 1000):
        raise RealtimeIndisponivel("expiresAt inválido")
    return {"capability": capability, "queryFingerprint": impressao, "expiresAt": expira}


def selar_consulta(consulta: str, parametros: dict[str, int], *, cliente: httpx.Client | None = None) -> dict:
    """Pede à Function `selarrt` a consulta selada. Levanta RealtimeIndisponivel em qualquer falha."""
    if not realtime_configurado():
        raise RealtimeIndisponivel("Realtime não configurado")
    corpo = json.dumps({"consulta": consulta, "parametros": parametros}, separators=(",", ":"), sort_keys=True)
    timestamp = str(int(time.time()))
    cabecalhos = {
        "content-type": "application/json",
        CABECALHO_TIMESTAMP: timestamp,
        CABECALHO_ASSINATURA: assinar(settings.REALTIME_SELO_SEGREDO, timestamp, corpo),
    }
    url = settings.NEON_SELARRT_URL.rstrip("/") + "/selar"
    try:
        if cliente is not None:
            resposta = cliente.post(url, content=corpo, headers=cabecalhos, timeout=TIMEOUT_SEGUNDOS)
        else:
            with httpx.Client(timeout=TIMEOUT_SEGUNDOS) as novo:
                resposta = novo.post(url, content=corpo, headers=cabecalhos)
    except httpx.HTTPError as erro:
        logger.warning("realtime: falha ao chamar a Function selarrt (%s)", type(erro).__name__)
        raise RealtimeIndisponivel("Function selarrt indisponível") from erro
    if resposta.status_code != 200:
        logger.warning("realtime: Function selarrt respondeu HTTP %s", resposta.status_code)
        raise RealtimeIndisponivel(f"Function selarrt respondeu {resposta.status_code}")
    try:
        return _validar_selada(resposta.json())
    except ValueError as erro:
        logger.warning("realtime: resposta da Function selarrt não é JSON válido")
        raise RealtimeIndisponivel("resposta inválida") from erro
