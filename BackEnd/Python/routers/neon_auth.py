"""Proxy do Neon Auth em /api/auth/neon/* (ativo só com AUTH_PROVIDER=neon).

Toda a lógica e as regras de segurança estão em services/neon_auth.py.
"""
from fastapi import APIRouter, Request
from fastapi.responses import Response

from services.neon_auth import encaminhar

router = APIRouter(prefix="/api/auth/neon", tags=["autenticacao"])


@router.api_route("/{caminho:path}", methods=["GET", "POST"], include_in_schema=False)
async def proxy_neon_auth(caminho: str, request: Request) -> Response:
    return await encaminhar(request, caminho)
