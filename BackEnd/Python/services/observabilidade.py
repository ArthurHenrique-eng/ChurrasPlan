"""Telemetria técnica sem URLs, query strings, cookies ou corpos."""
import json
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import Lock


class FormatoJSON(logging.Formatter):
    def format(self, record):
        dado = {"horario": datetime.now(UTC).isoformat(), "nivel": record.levelname, "logger": record.name,
                "evento": getattr(record, "evento", "log")}
        for campo in ("request_id", "metodo", "rota", "status", "duracao_ms", "tipo_erro"):
            if hasattr(record, campo):
                dado[campo] = getattr(record, campo)
        # Mensagens livres e stack traces podem conter chaves/PII; não entram neste handler.
        return json.dumps(dado, ensure_ascii=False)


def configurar_logs():
    logger = logging.getLogger("churrasplan")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(FormatoJSON())
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)


_lock = Lock()
_amostras = defaultdict(lambda: deque(maxlen=1000))
_contadores = defaultdict(int)


def medir(rota: str, status: int, duracao_ms: float):
    with _lock:
        _contadores[(rota, status)] += 1
        _amostras[rota].append(duracao_ms)


def metricas_http():
    with _lock:
        saida = []
        for rota, valores in _amostras.items():
            ordenados = sorted(valores)
            quantil = lambda p: round(ordenados[min(len(ordenados) - 1, int(len(ordenados) * p))], 2)
            saida.append({"rota": rota, "amostras": len(ordenados), "p50_ms": quantil(.5), "p95_ms": quantil(.95),
                          "p99_ms": quantil(.99), "requisicoes": sum(n for (r, s), n in _contadores.items() if r == rota),
                          "erros_5xx": sum(n for (r, s), n in _contadores.items() if r == rota and s >= 500)})
        return {"escopo": "processo_atual", "janela": "ultimas_1000_amostras_por_rota", "http": saida}
