"""Lista de compras ao vivo (Neon Realtime): autorização na API e chamada assinada à Function."""
import json
import time

import httpx
import pytest

from config import Settings, settings, validar_configuracao_producao
from services import realtime_neon
from tests.test_fases_3_a_6 import cadastro_login, payload_novo
from tests.test_integracao_churrascos import client  # noqa: F401  (fixture)

SEGREDO = "segredo-de-teste-com-32-caracteres!!"
URL_FUNCAO = "https://br-teste-selarrt.compute.exemplo.neon.tech"
URL_REALTIME = "wss://ep-teste.rt.exemplo.neon.tech/"


@pytest.fixture()
def realtime_ligado(monkeypatch):
    monkeypatch.setattr(settings, "NEON_REALTIME_URL", URL_REALTIME)
    monkeypatch.setattr(settings, "NEON_SELARRT_URL", URL_FUNCAO)
    monkeypatch.setattr(settings, "REALTIME_SELO_SEGREDO", SEGREDO)


def funcao_simulada(monkeypatch, responder):
    """Troca o transporte HTTP só das chamadas feitas por services.realtime_neon."""
    pedidos = []
    original = httpx.Client

    def handler(request: httpx.Request):
        pedidos.append(request)
        return responder(request)

    def fabrica(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(realtime_neon.httpx, "Client", fabrica)
    return pedidos


def selada_valida(_request=None):
    return httpx.Response(200, json={
        "capability": "cap-opaca",
        "queryFingerprint": "impressao",
        "expiresAt": int(time.time() * 1000) + 60_000,
    })


def churrasco_do_usuario(client, email="dono@example.com"):
    _, cabecalhos = cadastro_login(client, email=email)
    criado = client.post("/api/churrascos", json=payload_novo(chave_cliente=f"ao-vivo-{email}"), headers=cabecalhos)
    assert criado.status_code == 201, criado.text
    return criado.json()["id"], cabecalhos


def test_assinatura_igual_a_da_function_node():
    corpo = '{"consulta":"lista_compras_itens","parametros":{"lista_id":42}}'
    assert realtime_neon.assinar(SEGREDO, "1700000000", corpo) == (
        "f182f993ce91e7dd5c63ee03df21d47473b3a4c52a07d043deef08e3f308e4b0"
    )


def test_dono_recebe_consulta_selada_e_pedido_vai_assinado(client, realtime_ligado, monkeypatch):
    churrasco_id, cabecalhos = churrasco_do_usuario(client)
    pedidos = funcao_simulada(monkeypatch, selada_valida)

    r = client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo", headers=cabecalhos)

    assert r.status_code == 200, r.text
    assert "no-store" in r.headers["cache-control"]
    dados = r.json()
    assert dados["url"] == URL_REALTIME
    assert dados["consulta_selada"]["capability"] == "cap-opaca"
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert str(pedido.url) == URL_FUNCAO + "/selar"
    corpo = pedido.content.decode()
    lista_id = client.get(f"/api/lista-compras/{churrasco_id}").json()["id"]
    assert json.loads(corpo) == {"consulta": "lista_compras_itens", "parametros": {"lista_id": lista_id}}
    ts = pedido.headers["x-churrasplan-ts"]
    assert abs(int(ts) - time.time()) < 5
    assert pedido.headers["x-churrasplan-assinatura"] == realtime_neon.assinar(SEGREDO, ts, corpo)


def test_exige_sessao_e_csrf(client, realtime_ligado, monkeypatch):
    churrasco_id, _ = churrasco_do_usuario(client)
    pedidos = funcao_simulada(monkeypatch, selada_valida)
    assert client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo").status_code == 403
    client.cookies.clear()
    assert client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo").status_code == 401
    assert pedidos == []


def test_outro_usuario_nao_recebe_a_lista(client, realtime_ligado, monkeypatch):
    churrasco_id, _ = churrasco_do_usuario(client, email="dono@example.com")
    client.cookies.clear()
    _, cabecalhos_intruso = cadastro_login(client, email="intruso@example.com")
    pedidos = funcao_simulada(monkeypatch, selada_valida)

    r = client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo", headers=cabecalhos_intruso)

    assert r.status_code == 403
    assert pedidos == []


def test_churrasco_sem_dono_nao_tem_lista_ao_vivo(client, realtime_ligado, monkeypatch):
    anonimo = client.post("/api/churrascos", json=payload_novo(chave_cliente="ao-vivo-anonimo")).json()
    _, cabecalhos = cadastro_login(client, email="qualquer@example.com")
    pedidos = funcao_simulada(monkeypatch, selada_valida)

    r = client.post(f"/api/lista-compras/{anonimo['id']}/ao-vivo", headers=cabecalhos)

    assert r.status_code == 403
    assert pedidos == []


def test_lista_inexistente(client, realtime_ligado):
    _, cabecalhos = cadastro_login(client)
    assert client.post("/api/lista-compras/999999/ao-vivo", headers=cabecalhos).status_code == 404


def test_sem_configuracao_responde_503(client, monkeypatch):
    monkeypatch.setattr(settings, "NEON_REALTIME_URL", None)
    monkeypatch.setattr(settings, "NEON_SELARRT_URL", None)
    monkeypatch.setattr(settings, "REALTIME_SELO_SEGREDO", None)
    churrasco_id, cabecalhos = churrasco_do_usuario(client)
    assert client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo", headers=cabecalhos).status_code == 503


@pytest.mark.parametrize("responder", [
    lambda request: httpx.Response(500, json={"erro": "x"}),
    lambda request: httpx.Response(401, json={"erro": "assinatura_invalida"}),
    lambda request: httpx.Response(200, text="nao-e-json"),
    lambda request: httpx.Response(200, json={"capability": "c", "queryFingerprint": "f", "expiresAt": 1}),
    lambda request: httpx.Response(200, json={"queryFingerprint": "f", "expiresAt": 9_999_999_999_999}),
    lambda request: httpx.Response(200, json=["lista"]),
])
def test_falha_da_function_vira_503(client, realtime_ligado, monkeypatch, responder):
    churrasco_id, cabecalhos = churrasco_do_usuario(client)
    funcao_simulada(monkeypatch, responder)
    r = client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo", headers=cabecalhos)
    assert r.status_code == 503
    assert "cap" not in r.text


def test_timeout_da_function_vira_503(client, realtime_ligado, monkeypatch):
    churrasco_id, cabecalhos = churrasco_do_usuario(client)

    def estoura(request):
        raise httpx.ConnectTimeout("tempo esgotado", request=request)

    funcao_simulada(monkeypatch, estoura)
    assert client.post(f"/api/lista-compras/{churrasco_id}/ao-vivo", headers=cabecalhos).status_code == 503


def _producao(**valores):
    base = Settings()
    base.APP_ENV = "production"
    for chave, valor in valores.items():
        setattr(base, chave, valor)
    return base


def _erros_realtime(configuracao):
    with pytest.raises(RuntimeError) as erro:
        validar_configuracao_producao(configuracao)
    return [e for e in str(erro.value).split("; ") if "REALTIME" in e or "SELARRT" in e]


def test_producao_exige_as_tres_variaveis_juntas_e_seguras():
    parcial = _erros_realtime(_producao(NEON_REALTIME_URL=URL_REALTIME, NEON_SELARRT_URL=None, REALTIME_SELO_SEGREDO=None))
    assert any("configuradas juntas" in e for e in parcial)
    inseguro = _erros_realtime(_producao(
        NEON_REALTIME_URL="ws://inseguro", NEON_SELARRT_URL="http://inseguro", REALTIME_SELO_SEGREDO="curto"))
    assert len(inseguro) == 3
    correto = _producao(NEON_REALTIME_URL=URL_REALTIME, NEON_SELARRT_URL=URL_FUNCAO, REALTIME_SELO_SEGREDO=SEGREDO)
    try:
        validar_configuracao_producao(correto)
    except RuntimeError as erro:
        assert "REALTIME" not in str(erro) and "SELARRT" not in str(erro)
