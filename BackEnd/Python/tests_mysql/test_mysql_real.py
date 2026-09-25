import os
import uuid

import pytest
from sqlalchemy import inspect, text


pytestmark = pytest.mark.skipif(
    not os.getenv("MYSQL_TEST_URL"),
    reason="Defina MYSQL_TEST_URL para executar os testes contra MySQL real.",
)


def _setup_url():
    os.environ["DATABASE_URL"] = os.environ["MYSQL_TEST_URL"]
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "false")
    os.environ.setdefault("COOKIE_SECURE", "false")
    os.environ.setdefault("SECURITY_PEPPER", "mysql-test-pepper-012345678901234567890123456789")


def test_mysql_schema_head_e_utf8mb4():
    _setup_url()
    from database.connection import engine

    assert engine.dialect.name == "mysql"
    insp = inspect(engine)
    esperadas = {
        "usuarios", "churrascos", "produtos", "precos", "estabelecimentos",
        "consentimentos_usuario", "eventos_seguranca", "auditoria_admin",
    }
    assert esperadas.issubset(set(insp.get_table_names()))
    with engine.connect() as conn:
        head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        charset = conn.execute(text("SELECT @@character_set_database")).scalar_one()
    assert head == "20260925_0008"
    assert str(charset).lower() == "utf8mb4"


def test_mysql_fk_json_decimal_e_cascade():
    _setup_url()
    from database.connection import SessionLocal
    from models import ConsentimentoUsuario, Usuario
    from services.auth import hash_senha

    email = f"mysql-{uuid.uuid4().hex}@example.com"
    db = SessionLocal()
    try:
        u = Usuario(nome="Teste MySQL çã", email=email, senha_hash=hash_senha("SenhaMySQL123"), papel="usuario")
        db.add(u); db.flush()
        uid = u.id
        db.add(ConsentimentoUsuario(usuario_id=uid, tipo="privacidade", versao="teste", concedido=True, origem="mysql_ci"))
        db.commit()
        assert db.query(ConsentimentoUsuario).filter_by(usuario_id=uid).count() == 1
        db.delete(u); db.commit()
        assert db.query(ConsentimentoUsuario).filter_by(usuario_id=uid).count() == 0
    finally:
        db.close()


def test_mysql_production_readiness_schema_sem_ip_bruto_e_com_json():
    _setup_url()
    from database.connection import SessionLocal, engine
    from models import AuditoriaAdmin, Usuario
    from services.auth import hash_senha

    insp = inspect(engine)
    colunas_sessao = {c["name"] for c in insp.get_columns("sessoes_usuario")}
    assert "ip_hash" in colunas_sessao
    assert "ip_criado" not in colunas_sessao

    db = SessionLocal()
    try:
        admin = Usuario(
            nome="Admin MySQL", email=f"admin-{uuid.uuid4().hex}@example.com",
            senha_hash=hash_senha("SenhaAdminMySQL123"), papel="admin", ativo=True,
        )
        db.add(admin); db.flush()
        db.add(AuditoriaAdmin(
            admin_usuario_id=admin.id,
            acao="teste_mysql",
            entidade="sistema",
            entidade_id="ci",
            detalhes={"origem": "github-actions", "ok": True},
        ))
        db.commit()
        registro = db.query(AuditoriaAdmin).filter_by(acao="teste_mysql", admin_usuario_id=admin.id).one()
        assert registro.detalhes["ok"] is True
    finally:
        db.close()


def test_mysql_todas_as_tabelas_usam_innodb():
    _setup_url()
    from database.connection import engine

    with engine.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT TABLE_NAME, ENGINE
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
            """
        )).mappings().all()

    assert rows
    incorretas = [dict(r) for r in rows if str(r["ENGINE"]).lower() != "innodb"]
    assert incorretas == []
