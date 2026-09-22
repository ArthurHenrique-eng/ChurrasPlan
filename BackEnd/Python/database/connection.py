"""Conexão SQLAlchemy do ChurrasPlan.

A aplicação usa MySQL 8+ em produção e SQLite somente em testes unitários.
O pool é configurado explicitamente para MySQL para evitar conexões mortas em
instâncias long-lived atrás de proxies/balanceadores.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"pool_pre_ping": True, "echo": False}
    if url.startswith("mysql"):
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_timeout=30,
        )
    elif url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
