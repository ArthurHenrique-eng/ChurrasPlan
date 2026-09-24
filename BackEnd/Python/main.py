"""
Ponto de entrada da API do ChurrasPlan.

Para rodar localmente:
    uvicorn main:app --reload --port 8000

Documentacao interativa gerada automaticamente pelo FastAPI:
    http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text

from middleware.security import SecurityHeadersMiddleware

from config import settings, validar_configuracao_producao
from database.connection import engine, Base
import models  # noqa: F401  (garante que todos os models sejam registrados no Base)

validar_configuracao_producao()

from routers import calculadora, churrascos, produtos, estabelecimentos, precos, lista_compras, auth, convites, parceiros, onde_comprar, planos, privacidade, admin

# Conveniência estritamente local. A fonte de verdade do schema é Alembic;
# em produção AUTO_CREATE_SCHEMA é ignorado mesmo que alguém o habilite por engano.
if settings.AUTO_CREATE_SCHEMA and settings.APP_ENV != "production":
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="API do ChurrasPlan: planejamento, orçamento, convidados/RSVP, lista de compras, "
                 "preços reais, parceiros e otimização de onde comprar.",
    version="6.5.0",
)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
if settings.APP_ENV == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
    if settings.FORCE_HTTPS:
        app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(churrascos.router)
app.include_router(calculadora.router)
app.include_router(produtos.router)
app.include_router(estabelecimentos.router)
app.include_router(precos.router)
app.include_router(lista_compras.router)
app.include_router(auth.router)
app.include_router(convites.router)
app.include_router(parceiros.router)
app.include_router(onde_comprar.router)
app.include_router(planos.router)
app.include_router(privacidade.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health_check():
    """Liveness: confirma que o processo da API está respondendo."""
    return {"status": "ok", "app": settings.APP_NAME, "version": "6.5.0"}


@app.get("/api/health/ready", tags=["health"])
def readiness_check():
    """Readiness: confirma que a API também alcança o banco de dados."""
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    return {"status": "ready", "database": "ok", "version": "6.5.0"}
