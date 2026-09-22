from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
                    return JSONResponse({"detail": "Corpo da requisição excede o limite permitido."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Content-Length inválido."}, status_code=400)

        request_id = request.headers.get("x-request-id") or secrets.token_hex(12)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if request.url.path.startswith(("/api/auth", "/api/privacidade", "/api/admin")):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        if settings.APP_ENV == "production" and settings.FORCE_HTTPS:
            response.headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_SECONDS}; includeSubDomains"
        return response
