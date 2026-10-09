"""Fase 1 B2C — direitos efetivos, cota Free, recursos Premium e regressões."""
from datetime import datetime, timedelta, UTC

from database.connection import get_db
from models import AssinaturaStripeUsuario, Usuario
from services.relatorios_usuario import exportar_csv
from tests.test_integracao_churrascos import client, payload
from tests.test_billing_usuario_stripe import stripe_pessoal_fake
from tests.test_fases_3_a_6 import cadastro_login
from main import app


def _premium(client, fake, email):
    _, headers = cadastro_login(client, email)
    checkout = client.post("/api/billing/usuario/checkout", headers=headers, json={
        "plano": "premium", "periodicidade": "mensal", "chave_idempotencia": "premium-fase1-12345",
    })
    assert checkout.status_code == 201, checkout.text
    sessao = next(iter(fake["sessions"].values()))
    sessao["status"], sessao["payment_status"] = "complete", "paid"
    sync = client.post("/api/billing/usuario/sincronizar", headers=headers)
    assert sync.status_code == 200 and sync.json()["beneficios_ativos"], sync.text
    return headers


def _evento(client, chave, headers):
    return client.post("/api/churrascos", json=payload(chave_cliente=chave), headers=headers)


def test_free_cinco_planejamentos_mantem_historico_e_impede_mutacoes_adicionais(client):
    _, headers = cadastro_login(client, "free-cotas-b2c@example.com")
    b = client.get("/api/planos/meus-beneficios")
    assert b.status_code == 200
    assert b.json()["planejamentos"]["limite"] == 5
    assert b.json()["beneficios_ativos"] is False
    assert not b.json()["recursos"]["modelos_eventos"]

    eventos = []
    for n in range(5):
        r = _evento(client, f"free-fase1-evento-{n:02d}", headers)
        assert r.status_code == 201, r.text
        eventos.append(r.json()["id"])
    assert client.get("/api/planos/meus-beneficios").json()["planejamentos"]["uso"] == 5
    # Replay idempotente do mesmo planejamento não consome nova vaga.
    replay = _evento(client, "free-fase1-evento-00", headers)
    assert replay.status_code == 201 and replay.json()["id"] == eventos[0]
    negado = _evento(client, "free-fase1-evento-extra", headers)
    assert negado.status_code == 409
    assert negado.json()["detail"]["codigo"] == "LIMITE_PLANEJAMENTOS_FREE"
    assert client.post(f"/api/churrascos/{eventos[0]}/repetir", headers=headers, json={}).status_code == 409
    assert client.get("/api/churrascos/meus").status_code == 200
    assert client.get(f"/api/churrascos/{eventos[0]}").status_code == 200
    assert client.delete(f"/api/churrascos/{eventos[0]}", headers=headers).status_code == 204
    assert _evento(client, "free-fase1-depois-delete", headers).status_code == 201


def test_free_nao_burla_premium_e_dados_lgpd_continuam_livres(client):
    _, headers = cadastro_login(client, "free-acesso-b2c@example.com")
    ev = _evento(client, "free-b2c-seguranca-01", headers).json()["id"]
    assert client.get(f"/api/churrascos/{ev}/analise-custos").status_code == 403
    assert client.get(f"/api/churrascos/{ev}/exportar?formato=pdf").status_code == 403
    assert client.get(f"/api/churrascos/{ev}/exportar?formato=csv").status_code == 403
    assert client.post(f"/api/onde-comprar/churrasco/{ev}/comparacao-avancada", json={
        "modo": "equilibrio"}, headers=headers).status_code == 403
    assert client.post("/api/modelos-evento", headers=headers, json={
        "churrasco_id": ev, "nome": "Reutilizar churrasco",
    }).status_code == 403
    assert client.get("/api/privacidade/exportar").status_code == 200
    assert client.get(f"/api/onde-comprar/churrasco/{ev}").status_code == 200


def test_premium_recursos_reais_e_cota_ilimitada(client, stripe_pessoal_fake):
    headers = _premium(client, stripe_pessoal_fake, "premium-recursos-fase1@example.com")
    d = client.get("/api/planos/meus-beneficios").json()
    assert d["beneficios_ativos"] is True
    assert d["planejamentos"]["limite"] is None and d["planejamentos"]["ilimitado"]
    assert all(d["recursos"].values())

    eventos = []
    for n in range(7):
        resposta = _evento(client, f"premium-fase1-salvo-{n:02d}", headers)
        assert resposta.status_code == 201, resposta.text
        eventos.append(resposta.json()["id"])
    evento = eventos[0]
    custos = client.get(f"/api/churrascos/{evento}/analise-custos")
    assert custos.status_code == 200, custos.text
    detalhado = custos.json()
    assert detalhado["pessoas"] == 14 and detalhado["categorias"]
    assert detalhado["total_estimado_conhecido"] is not None

    csv_resp = client.get(f"/api/churrascos/{evento}/exportar?formato=csv")
    assert csv_resp.status_code == 200 and b"Preco unitario" in csv_resp.content
    assert csv_resp.headers["content-disposition"].endswith('.csv"')
    pdf_resp = client.get(f"/api/churrascos/{evento}/exportar?formato=pdf")
    assert pdf_resp.status_code == 200 and pdf_resp.content.startswith(b"%PDF")
    assert pdf_resp.headers["content-disposition"].endswith('.pdf"')

    compare = client.post(f"/api/onde-comprar/churrasco/{evento}/comparacao-avancada",
                          headers=headers, json={"modo": "preco"})
    assert compare.status_code == 200, compare.text
    assert compare.json()["lojas_com_ofertas"] >= 0
    assert compare.json()["observacao"].startswith("Comparação de ofertas cadastradas")

    assert client.post("/api/modelos-evento", json={
        "churrasco_id": evento, "nome": "Modelo para amigos",
    }).status_code == 403  # CSRF
    modelo = client.post("/api/modelos-evento", headers=headers, json={
        "churrasco_id": evento, "nome": "Modelo para amigos",
    })
    assert modelo.status_code == 201, modelo.text
    mid = modelo.json()["id"]
    assert len(client.get("/api/modelos-evento").json()) == 1
    novo = client.post(f"/api/modelos-evento/{mid}/usar", headers=headers, json={})
    assert novo.status_code == 201, novo.text
    assert novo.json()["usuario_id"] is not None


def test_modelos_escopo_e_downgrade_preservam_dados(client, stripe_pessoal_fake):
    headers = _premium(client, stripe_pessoal_fake, "premium-escopo-fase1@example.com")
    original = _evento(client, "premium-modelo-escopo-01", headers).json()["id"]
    modelo = client.post("/api/modelos-evento", headers=headers, json={
        "churrasco_id": original, "nome": "Modelo privado",
    }).json()["id"]
    _, outro = cadastro_login(client, "outro-usuario-fase1@example.com")
    assert client.get(f"/api/churrascos/{original}/analise-custos").status_code == 403
    assert client.post("/api/modelos-evento", headers=outro, json={
        "churrasco_id": original, "nome": "Falso",
    }).status_code == 403
    assert client.get("/api/modelos-evento").json() == []
    assert client.post(f"/api/modelos-evento/{modelo}/usar", headers=outro, json={}).status_code == 403
    assert client.delete(f"/api/modelos-evento/{modelo}", headers=outro).status_code == 404

    # Volta ao Premium com login anterior; simula assinatura expirada persistida.
    client.post("/api/auth/logout", headers=outro)
    cadastro_login(client, "premium-escopo-fase1@example.com")
    db = next(app.dependency_overrides[get_db]())
    try:
        usuario = db.query(Usuario).filter_by(email="premium-escopo-fase1@example.com").one()
        assinatura = db.get(AssinaturaStripeUsuario, usuario.id)
        assinatura.periodo_fim_em = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/planos/meus-beneficios").json()["beneficios_ativos"] is False
    assert client.get(f"/api/churrascos/{original}").status_code == 200
    assert client.get(f"/api/churrascos/{original}/exportar").status_code == 403
    assert client.get("/api/modelos-evento").json()[0]["id"] == modelo
    h = {"X-CSRF-Token": client.cookies.get("churrasplan_csrf")}
    assert client.post(f"/api/modelos-evento/{modelo}/usar", headers=h, json={}).status_code == 403
    assert client.delete(f"/api/modelos-evento/{modelo}", headers=h).status_code == 204


def test_csv_protege_formulas_de_planilhas():
    x = {"nome": "=SUM(1,1)", "pessoas": 1, "estimativa_completa": False,
         "itens": [{"nome": "=HYPERLINK(x)", "categoria": "+123", "quantidade_compra": 1,
                    "unidade_compra": "kg", "preco_estimado": 3.0,
                    "subtotal_estimado": 3.0, "preco_fonte": "@fake"}],
         "total_estimado_conhecido": 3.0, "aviso": "Preço de referência"}
    data = exportar_csv(x).decode("utf-8-sig")
    assert "'=HYPERLINK(x)" in data and "'+123" in data and "'@fake" in data
