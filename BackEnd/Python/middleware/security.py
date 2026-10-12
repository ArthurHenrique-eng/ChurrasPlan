from __future__ import annotations

import secrets
import logging
import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings
from services.observabilidade import medir, configurar_logs
configurar_logs()
logger = logging.getLogger("churrasplan.http")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origem = request.headers.get("origin")
            if origem and origem not in settings.CORS_ORIGINS and origem != settings.PUBLIC_APP_URL.rstrip("/"):
                return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
                    return JSONResponse({"detail": "Corpo da requisição excede o limite permitido."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Content-Length inválido."}, status_code=400)

        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            partes, tamanho = [], 0
            async for parte in request.stream():
                tamanho += len(parte)
                if tamanho > settings.MAX_REQUEST_BODY_BYTES:
                    return JSONResponse({"detail": "Corpo da requisição excede o limite permitido."}, status_code=413)
                partes.append(parte)
            request._body = b"".join(partes)

        informado = request.headers.get("x-request-id", "")
        request_id = informado if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", informado) else secrets.token_hex(12)
        inicio = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("request_error", extra={"evento": "request_error", "request_id": request_id, "tipo_erro": type(exc).__name__})
            response = JSONResponse({"detail": "Erro interno. Informe o código da requisição ao suporte."}, status_code=500)
        duracao = (time.monotonic() - inicio) * 1000
        rota = getattr(request.scope.get("route"), "path", "rota_desconhecida")
        medir(rota, response.status_code, duracao)
        logger.info("http_request", extra={"evento": "http_request", "request_id": request_id,
                    "metodo": request.method, "rota": rota, "status": response.status_code, "duracao_ms": round(duracao, 2)})
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        if settings.APP_ENV == "production" and settings.FORCE_HTTPS:
            response.headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_SECONDS}; includeSubDomains"
        return response
