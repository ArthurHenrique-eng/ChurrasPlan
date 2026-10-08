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
        "organizacoes", "organizacao_membros", "concessoes_organizacao",
    }
    assert esperadas.issubset(set(insp.get_table_names()))
    with engine.connect() as conn:
        head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        charset = conn.execute(text("SELECT @@character_set_database")).scalar_one()
    assert head == "20261008_0010"
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

def test_mysql_catalogo_generico_aplicado_por_migrations_sem_seed_demo():
    _setup_url()
    from config import CATALOGO_PRODUTOS_PADRAO
    from database.connection import SessionLocal
    from models import Categoria, Produto

    db = SessionLocal()
    try:
        categorias = {
            c.nome for c in db.query(Categoria).all()
        }
        esperadas = {
            "Carnes", "Bebidas", "Mercearia e alimentos", "Laticínios e frios",
            "Padaria", "Hortifruti", "Congelados", "Limpeza",
            "Higiene pessoal", "Descartáveis e utilidades",
        }
        assert esperadas.issubset(categorias)
        slugs = {
            p.slug for p in db.query(Produto)
            .filter(Produto.tipo_produto == "generico", Produto.ativo.is_(True)).all()
        }
        assert set(CATALOGO_PRODUTOS_PADRAO).issubset(slugs)
        assert {"detergente", "outro-produto-limpeza", "papel-higienico", "arroz", "agua"}.issubset(slugs)
        assert db.query(Produto).filter(
            Produto.slug == "detergente", Produto.tipo_produto == "generico"
        ).count() == 1
    finally:
        db.close()



def test_mysql_tenant_migration_backfill_preserva_dados():
    _setup_url()
    from database.connection import SessionLocal, engine
    from models import Estabelecimento, Organizacao, OrganizacaoMembro, Preco, Produto, Usuario

    insp = inspect(engine)
    assert {"organizacoes", "organizacao_membros", "concessoes_organizacao"}.issubset(insp.get_table_names())
    assert "organizacao_id" in {c["name"] for c in insp.get_columns("estabelecimentos")}
    assert "organizacao_id" in {c["name"] for c in insp.get_columns("produtos")}
    fk_est = {fk["name"] for fk in insp.get_foreign_keys("estabelecimentos")}
    fk_prod = {fk["name"] for fk in insp.get_foreign_keys("produtos")}
    assert "fk_estabelecimentos_organizacao_id" in fk_est
    assert "fk_produtos_organizacao_id" in fk_prod

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter_by(email="saas-legado-migracao@example.invalid").one()
        loja = db.query(Estabelecimento).filter_by(slug="saas-loja-legada-ci").one()
        sku = db.query(Produto).filter_by(slug="saas-produto-legado-ci").one()
        org = db.query(Organizacao).filter_by(slug=f"legado-parceiro-{usuario.id}").one()
        membro = db.query(OrganizacaoMembro).filter_by(
            organizacao_id=org.id, usuario_id=usuario.id
        ).one()
        assert membro.papel == "proprietario" and membro.ativo is True
        assert loja.usuario_responsavel_id == usuario.id
        assert loja.organizacao_id == org.id
        assert sku.organizacao_id == org.id
        compartilhado = db.query(Produto).filter_by(slug="saas-sku-ambiguo-ci").one()
        assert compartilhado.organizacao_id is None
        loja_sem_dono = db.query(Estabelecimento).filter_by(slug="saas-loja-sem-dono-ci").one()
        assert loja_sem_dono.organizacao_id is None
        assert db.query(Preco).filter_by(produto_id=compartilhado.id).count() == 2
        assert float(db.query(Preco).filter_by(
            produto_id=sku.id, estabelecimento_id=loja.id
        ).one().preco) == pytest.approx(3.79)
        assert db.query(OrganizacaoMembro).filter_by(
            organizacao_id=org.id, usuario_id=usuario.id
        ).count() == 1
    finally:
        db.close()



def test_mysql_cota_concorrente_mesma_organizacao(monkeypatch):
    """Dois escritores simultâneos não ultrapassam o limite da organização."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi import HTTPException
    from database.connection import SessionLocal
    from models import Estabelecimento, Organizacao, Usuario
    from services.entitlements import LIMITES_PLANOS, exigir_cota_criacao

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter_by(email="saas-legado-migracao@example.invalid").one()
        org = db.query(Organizacao).filter_by(slug=f"legado-parceiro-{usuario.id}").one()
        org_id, uid = org.id, usuario.id
        existentes = db.query(Estabelecimento).filter_by(organizacao_id=org_id).count()
    finally:
        db.close()
    monkeypatch.setitem(LIMITES_PLANOS["free"], "estabelecimentos", existentes + 1)
    inicio = Barrier(2)

    def criar(i):
        sessao = SessionLocal()
        try:
            u = sessao.get(Usuario, uid)
            o = sessao.get(Organizacao, org_id)
            inicio.wait(timeout=20)
            exigir_cota_criacao(sessao, o, u, "estabelecimentos")
            sessao.add(Estabelecimento(
                usuario_responsavel_id=uid, organizacao_id=org_id,
                nome=f"Loja quota concorrente {i}", slug=f"quota-ci-{uuid.uuid4().hex}",
                tipo="mercado", parceiro_verificado=False, ativo=True,
            ))
            sessao.commit()
            return 201
        except HTTPException as exc:
            sessao.rollback()
            return exc.status_code
        finally:
            sessao.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(criar, (1, 2)))
    assert sorted(resultados) == [201, 409]
    db = SessionLocal()
    try:
        assert db.query(Estabelecimento).filter_by(organizacao_id=org_id).count() == existentes + 1
    finally:
        db.close()
