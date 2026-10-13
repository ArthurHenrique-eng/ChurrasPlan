"""Fase 2A: isolamento de organização em endpoints B2B.

O papel global 'parceiro' não permite ler nem alterar dados de outras
organizações; a seleção de tenant é verificada no backend.
"""
from fastapi.testclient import TestClient

from database.connection import get_db
from main import app
from models import Organizacao, OrganizacaoMembro, Usuario
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client


def _ativar(cliente, headers):
    r = cliente.post("/api/parceiro/ativar", headers=headers)
    assert r.status_code == 200, r.text
    orgs = cliente.get("/api/parceiro/organizacoes")
    assert orgs.status_code == 200, orgs.text
    assert len(orgs.json()) == 1
    assert orgs.json()[0]["papel"] == "proprietario"
    return orgs.json()[0]["id"]


def _mercado(cliente, headers, nome):
    r = cliente.post(
        "/api/parceiro/estabelecimentos", headers=headers,
        json={"nome": nome, "tipo": "mercado"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _sku(cliente, headers, nome, marca):
    base = cliente.get("/api/produtos/genericos")
    assert base.status_code == 200
    pai = next(p for p in base.json() if p["slug"] == "agua")
    r = cliente.post("/api/parceiro/produtos", headers=headers, json={
        "produto_pai_id": pai["id"], "nome": nome, "marca": marca,
        "unidade_venda": "garrafa", "quantidade_embalagem": 1,
        "unidade_embalagem": "litro",
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_ativacao_idempotente_cria_org_do_parceiro(client):
    _, h = cadastro_login(client, "saas-org-ativar@example.com")
    org_id = _ativar(client, h)
    assert client.post("/api/parceiro/ativar", headers=h).status_code == 200
    orgs = client.get("/api/parceiro/organizacoes").json()
    assert [x["id"] for x in orgs] == [org_id]
    assert orgs[0]["slug"].startswith("parceiro-")


def test_parceiros_nao_leem_ou_escrevem_dados_de_outra_org(client):
    _, ha = cadastro_login(client, "tenant-a@example.com")
    org_a = _ativar(client, ha)
    loja_a = _mercado(client, ha, "Mercado da Organização A")
    produto_a = _sku(client, ha, "Água A 1L", "Marca A")
    assert loja_a["organizacao_id"] == org_a
    assert produto_a["organizacao_id"] == org_a
    assert client.post("/api/parceiro/precos", headers=ha, json={
        "estabelecimento_id": loja_a["id"], "produto_id": produto_a["id"], "preco": 3.5,
    }).status_code == 201

    with TestClient(app) as outro:
        _, hb = cadastro_login(outro, "tenant-b@example.com")
        org_b = _ativar(outro, hb)
        loja_b = _mercado(outro, hb, "Mercado da Organização B")
        produto_b = _sku(outro, hb, "Água B 1L", "Marca B")
        assert loja_b["organizacao_id"] == org_b
        assert produto_b["organizacao_id"] == org_b

        # Mesmo que o browser tente declarar o ID da organização A,
        # o backend verifica a participação e retorna 404.
        for rota in ["/api/parceiro/estabelecimentos", "/api/parceiro/produtos",
                     "/api/parceiro/dashboard"]:
            assert outro.get(rota, headers={"X-Organizacao-ID": str(org_a)}).status_code == 404

        ests = outro.get("/api/parceiro/estabelecimentos").json()
        assert [x["id"] for x in ests] == [loja_b["id"]]
        assert [x["id"] for x in outro.get("/api/parceiro/produtos").json()] == [produto_b["id"]]
        assert outro.get("/api/parceiro/dashboard").json()["estabelecimentos"] == 1

        assert outro.put(
            f"/api/parceiro/estabelecimentos/{loja_a['id']}", headers=hb,
            json={"nome": "Ataque de outro tenant", "tipo": "mercado"},
        ).status_code == 404
        assert outro.post("/api/parceiro/precos", headers=hb, json={
            "estabelecimento_id": loja_a["id"],
            "produto_id": produto_b["id"], "preco": 1,
        }).status_code == 404
        assert outro.post("/api/parceiro/precos", headers=hb, json={
            "estabelecimento_id": loja_b["id"],
            "produto_id": produto_a["id"], "preco": 1,
        }).status_code == 404
        assert outro.get("/api/parceiro/organizacoes").json()[0]["id"] == org_b

    assert [e["id"] for e in client.get("/api/parceiro/estabelecimentos").json()] == [loja_a["id"]]
    assert [p["id"] for p in client.get("/api/parceiro/produtos").json()] == [produto_a["id"]]


def test_multiplas_organizacoes_exigem_header_e_leitor_nao_edita(client):
    _, ha = cadastro_login(client, "org-dono@example.com")
    org_a = _ativar(client, ha)
    loja_a = _mercado(client, ha, "Loja compartilhada")
    with TestClient(app) as outro:
        _, hb = cadastro_login(outro, "org-leitor@example.com")
        org_b = _ativar(outro, hb)
        db = next(app.dependency_overrides[get_db]())
        try:
            leitor = db.query(Usuario).filter(Usuario.email == "org-leitor@example.com").one()
            db.add(OrganizacaoMembro(
                organizacao_id=org_a, usuario_id=leitor.id, papel="leitor",
                ativo=True,
            ))
            db.commit()
        finally:
            db.close()

        assert outro.get("/api/parceiro/estabelecimentos").status_code == 409
        assert outro.get("/api/parceiro/dashboard").status_code == 409
        assert outro.get("/api/parceiro/produtos").status_code == 409

        contexto = {"X-Organizacao-ID": str(org_a)}
        assert [e["id"] for e in outro.get(
            "/api/parceiro/estabelecimentos", headers=contexto,
        ).json()] == [loja_a["id"]]

        escrita = {**hb, **contexto}
        assert outro.post("/api/parceiro/estabelecimentos", headers=escrita,
                          json={"nome": "Loja não autorizada"}).status_code == 403
        assert outro.put(f"/api/parceiro/estabelecimentos/{loja_a['id']}",
                         headers=escrita,
                         json={"nome": "Alteração indevida"}).status_code == 403

        propria = {"X-Organizacao-ID": str(org_b)}
        assert outro.get("/api/parceiro/estabelecimentos", headers=propria).json() == []
        orgs = outro.get("/api/parceiro/organizacoes").json()
        assert {x["id"] for x in orgs} == {org_a, org_b}


def test_organizacao_inexistente_falha_fechado(client):
    _, h = cadastro_login(client, "org-negada@example.com")
    _ativar(client, h)
    assert client.get("/api/parceiro/estabelecimentos",
                      headers={"X-Organizacao-ID": "999999"}).status_code == 404
    assert client.post("/api/parceiro/produtos",
                       headers={**h, "X-Organizacao-ID": "999999"},
                       json={"produto_pai_id": 1, "nome": "Item", "marca": "X",
                             "unidade_venda": "un", "quantidade_embalagem": 1,
                             "unidade_embalagem": "un"}).status_code == 404



def test_promocao_admin_cria_organizacao_e_desbloqueia_painel(client):
    from database.connection import get_db
    from main import app
    from models import OrganizacaoMembro, Usuario
    from services.auth import hash_senha

    _, _ = cadastro_login(client, "parceiro-promovido@example.com")
    db = next(app.dependency_overrides[get_db]())
    try:
        parceiro = db.query(Usuario).filter_by(email="parceiro-promovido@example.com").one()
        uid = parceiro.id
        db.add(Usuario(
            nome="Administrador", email="admin-promocao@example.com",
            senha_hash=hash_senha("SenhaPromocao123"), papel="admin", ativo=True,
        ))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as admin_client:
        login = admin_client.post("/api/auth/login", json={
            "email": "admin-promocao@example.com", "senha": "SenhaPromocao123"
        })
        assert login.status_code == 200, login.text
        csrf = admin_client.cookies.get("churrasplan_csrf")
        promovido = admin_client.patch(
            f"/api/admin/usuarios/{uid}",
            headers={"X-CSRF-Token": csrf},
            json={"papel": "parceiro"},
        )
        assert promovido.status_code == 200, promovido.text

    # Usuário já logado foi promovido; o painel deve funcionar sem reativar.
    assert client.get("/api/auth/me").json()["papel"] == "parceiro"
    orgs = client.get("/api/parceiro/organizacoes")
    assert orgs.status_code == 200 and len(orgs.json()) == 1
    assert orgs.json()[0]["papel"] == "proprietario"
    assert client.get("/api/parceiro/estabelecimentos").status_code == 200
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(OrganizacaoMembro).filter_by(usuario_id=uid).count() == 1
    finally:
        db.close()
