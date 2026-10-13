"""Fase 2C: autorização de equipe, convite por e-mail e seleção multi-org."""
from datetime import timedelta

from fastapi.testclient import TestClient

from database.connection import get_db
from main import app
from models import AuditoriaOrganizacao, ConviteOrganizacao, OrganizacaoMembro, Usuario
from services.auth import agora, hash_token
from services.equipe_organizacao import LIMITES_MEMBROS
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_integracao_churrascos import client
from tests.test_tenants_saas import _ativar, _mercado


def convite(cliente, headers, email, papel="leitor", org_id=None):
    h = {**headers}
    if org_id: h["X-Organizacao-ID"] = str(org_id)
    return cliente.post("/api/parceiro/equipe/convites", headers=h,
                        json={"email": email, "papel": papel})


def test_convite_one_time_vinculado_email_e_isolamento(client):
    _, h_dono = cadastro_login(client, "dono-c@example.com")
    org = _ativar(client, h_dono)
    enviado = convite(client, h_dono, "Convidado-C@Example.Com", "editor")
    assert enviado.status_code == 201, enviado.text
    token = enviado.json()["dev_token"]
    assert token and enviado.json()["enviado"] is False
    assert enviado.json()["email"] == "convidado-c@example.com"
    db = next(app.dependency_overrides[get_db]())
    try:
        registro = db.query(ConviteOrganizacao).filter_by(organizacao_id=org).one()
        assert registro.token_hash == hash_token(token)
        assert registro.token_hash != token
        assert registro.usado_em is None
    finally:
        db.close()
    pendentes = client.get("/api/parceiro/equipe/convites")
    assert pendentes.status_code == 200
    assert "dev_token" not in str(pendentes.json())
    assert "token_hash" not in str(pendentes.json())

    with TestClient(app) as errado:
        _, he = cadastro_login(errado, "outra-c@example.com")
        negado = errado.post("/api/parceiro/convites/aceitar", headers=he, json={"token": token})
        assert negado.status_code == 404, negado.text
        assert errado.get("/api/parceiro/organizacoes").status_code == 403
        assert errado.post("/api/parceiro/convites/aceitar", json={"token": token}).status_code == 403

    with TestClient(app) as convidado:
        _, hc = cadastro_login(convidado, "convidado-c@example.com")
        assert convidado.post("/api/parceiro/convites/aceitar", headers=hc,
                              json={"token": token}).status_code == 200
        assert convidado.post("/api/parceiro/convites/aceitar", headers=hc,
                              json={"token": token}).status_code == 404
        orgs = convidado.get("/api/parceiro/organizacoes")
        assert orgs.status_code == 200, orgs.text
        assert orgs.json()[0]["id"] == org and orgs.json()[0]["papel"] == "editor"
        assert convidado.get("/api/auth/me").json()["papel"] == "parceiro"
        assert convidado.get("/api/parceiro/dashboard").status_code == 200
        loja = _mercado(convidado, hc, "Loja do Editor")
        assert loja["organizacao_id"] == org
        assert convidado.get("/api/parceiro/equipe/membros").status_code == 403
        assert convite(convidado, hc, "terceiro@example.com").status_code == 403
        assert convidado.get("/api/parceiro/entitlements").json()["equipe"]["ativos"] == 2

    auditoria = client.get("/api/parceiro/equipe/membros").json()
    assert len(auditoria) == 2
    assert {m["papel"] for m in auditoria} == {"proprietario", "editor"}
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(AuditoriaOrganizacao).filter_by(
            organizacao_id=org, acao="convite_aceito"
        ).count() == 1
    finally: db.close()


def test_permissoes_gestor_proprietario_e_remocao(client):
    _, hd = cadastro_login(client, "dono-roles@example.com")
    org = _ativar(client, hd)
    with TestClient(app) as gestor:
        _, hg = cadastro_login(gestor, "gestor-roles@example.com")
        invite = convite(client, hd, "gestor-roles@example.com", "gestor")
        assert invite.status_code == 201
        assert gestor.post("/api/parceiro/convites/aceitar", headers=hg,
                           json={"token": invite.json()["dev_token"]}).status_code == 200
        gestor_id = gestor.get("/api/auth/me").json()["id"]
        assert convite(gestor, hg, "leitor-roles@example.com", "leitor").status_code == 201
        assert convite(gestor, hg, "dono2@example.com", "proprietario").status_code == 403
        assert convite(gestor, hg, "gestor2@example.com", "gestor").status_code == 403
        assert gestor.patch(f"/api/parceiro/equipe/membros/{gestor_id}", headers=hg,
                            json={"papel": "leitor"}).status_code == 422

        with TestClient(app) as leitor:
            _, hl = cadastro_login(leitor, "leitor-roles@example.com")
            le = next(c for c in gestor.get("/api/parceiro/equipe/convites").json()
                      if c["email"] == "leitor-roles@example.com")
            # A API nunca devolve token: o proprietário pode obter apenas o link do envio dev.
            # Criamos aqui um segundo convite para exercer o aceite do leitor.
            assert gestor.delete(f"/api/parceiro/equipe/convites/{le['id']}", headers=hg).status_code == 200
            fresh = convite(gestor, hg, "leitor-roles@example.com", "leitor")
            assert leitor.post("/api/parceiro/convites/aceitar", headers=hl,
                               json={"token": fresh.json()["dev_token"]}).status_code == 200
            leitor_id = leitor.get("/api/auth/me").json()["id"]
            assert leitor.get("/api/parceiro/dashboard").status_code == 200
            assert leitor.get("/api/parceiro/equipe/membros").status_code == 403
            assert leitor.post("/api/parceiro/estabelecimentos", headers=hl,
                               json={"nome": "Negado"}).status_code == 403
            assert gestor.patch(f"/api/parceiro/equipe/membros/{leitor_id}", headers=hg,
                                json={"papel": "editor"}).status_code == 200
            assert leitor.post("/api/parceiro/estabelecimentos", headers=hl,
                               json={"nome": "Permitido", "tipo": "mercado"}).status_code == 201
            assert gestor.delete(f"/api/parceiro/equipe/membros/{leitor_id}", headers=hg).status_code == 200
            assert leitor.get("/api/parceiro/dashboard").status_code == 404
            assert leitor.get("/api/parceiro/organizacoes").json() == []
            assert leitor.get("/api/auth/me").status_code == 200

        assert gestor.delete(f"/api/parceiro/equipe/membros/{gestor_id}", headers=hg).status_code == 422
        assert gestor.delete(f"/api/parceiro/equipe/membros/{client.get('/api/auth/me').json()['id']}",
                             headers=hg).status_code == 403
        assert client.patch(f"/api/parceiro/equipe/membros/{gestor_id}", headers=hd,
                            json={"papel": "proprietario"}).status_code == 200
        assert client.delete(f"/api/parceiro/equipe/membros/{gestor_id}", headers=hd).status_code == 200
        assert gestor.get("/api/parceiro/dashboard").status_code == 404
    assert client.get("/api/parceiro/equipe/membros").json()[0]["papel"] == "proprietario"
    assert client.patch(f"/api/parceiro/equipe/membros/{client.get('/api/auth/me').json()['id']}",
                        headers=hd, json={"papel": "editor"}).status_code == 422


def test_convites_lotacao_revogacao_expiracao_e_csrf(client, monkeypatch):
    monkeypatch.setitem(LIMITES_MEMBROS, "free", 2)
    _, hd = cadastro_login(client, "dono-quota2c@example.com")
    org = _ativar(client, hd)
    assert client.post("/api/parceiro/equipe/convites",
                       json={"email": "pessoa@example.com", "papel": "leitor"}).status_code == 403
    first = convite(client, hd, "pessoa@example.com")
    assert first.status_code == 201
    assert convite(client, hd, "pessoa@example.com").status_code == 409
    full = convite(client, hd, "pessoa2@example.com")
    assert full.status_code == 409
    assert full.json()["detail"]["codigo"] == "LIMITE_MEMBROS_ATINGIDO"
    assert client.get("/api/parceiro/entitlements").json()["equipe"] == {
        "ativos": 1, "convites_pendentes": 1, "limite": 2
    }
    assert client.delete(f"/api/parceiro/equipe/convites/{first.json()['id']}",
                         headers=hd).status_code == 200
    with TestClient(app) as convidado:
        _, hc = cadastro_login(convidado, "pessoa@example.com")
        assert convidado.post("/api/parceiro/convites/aceitar", headers=hc,
                              json={"token": first.json()["dev_token"]}).status_code == 404
    second = convite(client, hd, "pessoa2@example.com")
    assert second.status_code == 201
    db = next(app.dependency_overrides[get_db]())
    try:
        c = db.get(ConviteOrganizacao, second.json()["id"])
        c.expira_em = agora()-timedelta(seconds=1)
        db.commit()
    finally: db.close()
    assert convite(client, hd, "pessoa3@example.com").status_code == 201
    assert len(client.get("/api/parceiro/equipe/convites").json()) == 1


def test_multiorg_header_e_admin_sem_participacao(client):
    _, ha = cadastro_login(client, "dono-multi-c@example.com")
    org_a = _ativar(client, ha)
    with TestClient(app) as outro:
        _, hb = cadastro_login(outro, "outro-multi-c@example.com")
        org_b = _ativar(outro, hb)
        c = convite(client, ha, "outro-multi-c@example.com", org_id=org_a)
        assert outro.post("/api/parceiro/convites/aceitar", headers=hb,
                          json={"token": c.json()["dev_token"]}).status_code == 200
        assert outro.get("/api/parceiro/entitlements").status_code == 409
        assert outro.get("/api/parceiro/equipe/membros").status_code == 409
        assert outro.get("/api/parceiro/dashboard", headers={"X-Organizacao-ID": str(org_a)}).status_code == 200
        assert outro.get("/api/parceiro/dashboard", headers={"X-Organizacao-ID": str(org_b)}).status_code == 200
        assert outro.get("/api/parceiro/dashboard", headers={"X-Organizacao-ID": "999999"}).status_code == 404
        assert client.get("/api/parceiro/equipe/membros", headers={"X-Organizacao-ID": str(org_b)}).status_code == 404
        assert convite(client, ha, "qualquer@example.com", org_id=org_b).status_code == 404
        # O membro leitor não pode administrar o tenant alheio mesmo com header válido.
        assert outro.get("/api/parceiro/equipe/membros", headers={"X-Organizacao-ID": str(org_a)}).status_code == 403



def test_admin_global_nao_pode_administrar_equipe_sem_membership(client):
    from tests.test_entitlements_saas import _admin_logado
    _, h = cadastro_login(client, "dono-admin-scope@example.com")
    org = _ativar(client, h)
    admin, ha = _admin_logado()
    with admin:
        contexto = {"X-Organizacao-ID": str(org)}
        assert admin.get("/api/parceiro/dashboard", headers=contexto).status_code == 200
        assert admin.get("/api/parceiro/equipe/membros", headers=contexto).status_code == 404
        assert admin.get("/api/parceiro/equipe/convites", headers=contexto).status_code == 404
        assert admin.post("/api/parceiro/equipe/convites",
                          headers={**ha, **contexto},
                          json={"email": "terceiro@example.com", "papel": "proprietario"}).status_code == 404


def test_convite_expirado_nao_pode_ser_aceito(client):
    _, h = cadastro_login(client, "dono-expire2c@example.com")
    org = _ativar(client, h)
    c = convite(client, h, "invite-expire2c@example.com")
    assert c.status_code == 201
    db = next(app.dependency_overrides[get_db]())
    try:
        registro = db.get(ConviteOrganizacao, c.json()["id"])
        registro.expira_em = agora() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    with TestClient(app) as convidado:
        _, hc = cadastro_login(convidado, "invite-expire2c@example.com")
        usado = convidado.post("/api/parceiro/convites/aceitar", headers=hc,
                               json={"token": c.json()["dev_token"]})
        assert usado.status_code == 404
        assert convidado.get("/api/auth/me").json()["papel"] == "usuario"
    assert client.get("/api/parceiro/equipe/convites").json() == []
