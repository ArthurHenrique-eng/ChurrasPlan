import pytest

from tests.test_integracao_churrascos import client


def registrar(client, email="lgpd@example.com"):
    r = client.post("/api/auth/register", json={
        "nome": "Pessoa LGPD", "email": email, "senha": "SenhaForte123",
        "aceite_termos": True, "aceite_privacidade": True, "aceite_marketing": False,
    })
    assert r.status_code == 201, r.text
    csrf = client.cookies.get("churrasplan_csrf")
    return r.json(), {"X-CSRF-Token": csrf}


def test_cadastro_exige_aceites_legais(client):
    r = client.post("/api/auth/register", json={
        "nome": "Sem Aceite", "email": "sem-aceite@example.com", "senha": "SenhaForte123",
    })
    assert r.status_code == 422
    assert "Termos" in r.text or "Privacidade" in r.text


def test_consentimentos_exportacao_e_marketing(client):
    registrar(client)
    consentimentos = client.get("/api/privacidade/meus-consentimentos")
    assert consentimentos.status_code == 200
    tipos = {c["tipo"]: c for c in consentimentos.json()}
    assert tipos["termos"]["concedido"] is True
    assert tipos["privacidade"]["concedido"] is True
    assert tipos["marketing"]["concedido"] is False

    csrf = client.cookies.get("churrasplan_csrf")
    r = client.put("/api/privacidade/marketing", json={"concedido": True}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert r.json()["concedido"] is True

    export = client.get("/api/privacidade/exportar")
    assert export.status_code == 200
    dados = export.json()
    assert dados["formato"] == "ChurrasPlan-LGPD-export-v1"
    assert dados["usuario"]["email"] == "lgpd@example.com"
    assert "senha_hash" not in dados["usuario"]


def test_exclusao_conta_exige_senha_e_remove_login(client):
    registrar(client, "excluir@example.com")
    csrf = client.cookies.get("churrasplan_csrf")
    r = client.request("DELETE", "/api/privacidade/minha-conta", json={"senha":"SenhaForte123","confirmacao":"EXCLUIR"}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me").status_code == 401


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "x-request-id" in r.headers


def test_rate_limit_login(client, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    for _ in range(2):
        r = client.post("/api/auth/login", json={"email":"rate@example.com","senha":"SenhaErrada123"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email":"rate@example.com","senha":"SenhaErrada123"})
    assert r.status_code == 429


def test_admin_dashboard_moderacao_e_auditoria(client):
    from database.connection import get_db
    from main import app
    from models import Usuario
    from services.auth import hash_senha

    # Usa a sessão do fixture para criar o admin diretamente, como faria o script create_admin.py.
    db = next(app.dependency_overrides[get_db]())
    try:
        admin = Usuario(nome="Admin", email="admin@example.com", senha_hash=hash_senha("SenhaAdmin123"), papel="admin", ativo=True)
        db.add(admin); db.commit()
    finally:
        db.close()

    login = client.post("/api/auth/login", json={"email":"admin@example.com","senha":"SenhaAdmin123"})
    assert login.status_code == 200, login.text
    csrf = client.cookies.get("churrasplan_csrf")
    h = {"X-CSRF-Token": csrf}
    dash = client.get("/api/admin/dashboard")
    assert dash.status_code == 200
    assert dash.json()["usuarios"] >= 1

    # Cria outro usuário via ORM para não trocar a sessão do admin.
    db = next(app.dependency_overrides[get_db]())
    try:
        u = Usuario(nome="Moderado", email="moderado@example.com", senha_hash=hash_senha("SenhaModerado123"), papel="usuario", ativo=True)
        db.add(u); db.commit(); uid = u.id
    finally:
        db.close()
    alterado = client.patch(f"/api/admin/usuarios/{uid}", json={"papel":"parceiro"}, headers=h)
    assert alterado.status_code == 200, alterado.text
    assert alterado.json()["papel"] == "parceiro"
    auditoria = client.get("/api/admin/auditoria")
    assert auditoria.status_code == 200
    assert any(x["acao"] == "usuario_atualizado" for x in auditoria.json())



def test_preparar_admin_verifica_email_e_redefine_senha(client):
    from database.connection import get_db
    from main import app
    from scripts.create_admin import preparar_admin
    from services.auth import verificar_senha

    db = next(app.dependency_overrides[get_db]())
    try:
        admin = preparar_admin(
            db,
            email="bootstrap-admin@example.com",
            senha="SenhaAdminInicial123",
            nome="Admin Bootstrap",
            redefinir_senha=True,
        )
        assert admin.papel == "admin"
        assert admin.ativo is True
        assert admin.email_verificado_em is not None
        assert verificar_senha("SenhaAdminInicial123", admin.senha_hash)

        admin2 = preparar_admin(
            db,
            email="bootstrap-admin@example.com",
            senha="SenhaAdminNova456",
            nome="Admin Bootstrap",
            redefinir_senha=True,
        )
        assert admin2.id == admin.id
        assert verificar_senha("SenhaAdminNova456", admin2.senha_hash)
        assert not verificar_senha("SenhaAdminInicial123", admin2.senha_hash)
    finally:
        db.close()

def test_readiness_verifica_banco(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"


def test_seed_demo_cobre_catalogo_padrao():
    from config import CATALOGO_PRODUTOS_PADRAO
    from scripts.seed_demo import PRECOS_DEMO

    assert set(PRECOS_DEMO) == set(CATALOGO_PRODUTOS_PADRAO)
