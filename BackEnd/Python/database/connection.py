"""Conexão SQLAlchemy do ChurrasPlan.

A aplicação usa PostgreSQL em produção (MySQL 8+ continua suportado) e SQLite
somente em testes unitários. O pool é configurado explicitamente para os bancos
de servidor, evitando conexões mortas em instâncias long-lived atrás de
proxies/balanceadores e em bancos serverless que suspendem por inatividade.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

# Falha rápida quando o banco não responde, em vez de prender a requisição.
CONNECT_TIMEOUT_SEGUNDOS = 10


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"pool_pre_ping": True, "echo": False}
    if url.startswith(("mysql", "postgresql")):
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_timeout=30,
        )
    if url.startswith("postgresql"):
        if "connect_timeout" not in make_url(url).query:
            kwargs["connect_args"] = {"connect_timeout": CONNECT_TIMEOUT_SEGUNDOS}
    elif url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


def configurar_sessao_postgresql(engine: Engine) -> None:
    """Fixa o fuso da sessão em UTC.

    Colunas DateTime sem fuso recebem ``now()`` do banco e são comparadas com
    ``services.auth.agora()`` (UTC sem tzinfo). O MySQL já roda em UTC nos
    ambientes do projeto; no PostgreSQL o fuso vem da configuração do servidor,
    então a sessão o define explicitamente.
    """
    if engine.dialect.name != "postgresql":
        return

    @event.listens_for(engine, "connect")
    def _fuso_utc(dbapi_connection, _connection_record):
        autocommit_original = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
        dbapi_connection.autocommit = autocommit_original


def contagem_com_bloqueio(db, stmt):
    """Aplica FOR UPDATE a um SELECT COUNT(...) apenas no MySQL.

    Quem chama já bloqueou a linha pai (usuário ou organização), o que
    serializa os escritores concorrentes. No InnoDB (REPEATABLE READ) o
    FOR UPDATE faz a contagem ler o estado corrente em vez do snapshot da
    transação. O PostgreSQL recusa FOR UPDATE com funções de agregação e, em
    READ COMMITTED (padrão), cada comando já enxerga o que foi confirmado
    antes dele, inclusive o que a transação que segurava o lock gravou.
    """
    return stmt.with_for_update() if db.get_bind().dialect.name == "mysql" else stmt


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))
configurar_sessao_postgresql(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
