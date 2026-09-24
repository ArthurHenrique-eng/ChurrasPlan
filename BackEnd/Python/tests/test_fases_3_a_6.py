import pytest
from tests.test_integracao_churrascos import client


def cadastro_login(client, email="arthur@example.com"):
    r = client.post("/api/auth/register", json={"nome":"Arthur","email":email,"senha":"SenhaForte123","aceite_termos":True,"aceite_privacidade":True})
    assert r.status_code == 201, r.text
    csrf = client.cookies.get("churrasplan_csrf")
    assert csrf
    return r.json(), {"X-CSRF-Token": csrf}


def payload_novo(**overrides):
    p={
        "chave_cliente":"planejamento-fase3-0001", "nome":"Churrasco teste", "tipo_evento":"almoco",
        "duracao_horas":4, "perfil_consumo":"normal", "adultos":10, "adultos_bebem_alcool":4, "criancas":2,
        "vegetarianos":1, "veganos":1, "sem_carne_bovina":1, "sem_carne_suina":0, "intolerantes_lactose":1,
        "orcamento_maximo":300, "carnes":[{"nome":"Picanha","produto_slug":"picanha","percentual":100}],
        "carvao_ativo":True, "bebidas_nao_alcoolicas_ativas":[], "bebida_alcoolica_ativa":False,
        "gelo_ativo":False, "extras_ativos":[], "acompanhamentos_ativos":[],
    }
    p.update(overrides); return p


def test_registro_cria_sessao_http_cookie_e_me(client):
    d,_=cadastro_login(client)
    assert d["usuario"]["papel"] == "usuario"
    assert client.cookies.get("churrasplan_session")
    me=client.get("/api/auth/me")
    assert me.status_code==200
    assert me.json()["email"]=="arthur@example.com"


def test_mutacao_autenticada_exige_csrf(client):
    cadastro_login(client)
    r=client.post("/api/churrascos", json=payload_novo())
    assert r.status_code==403


def test_orcamento_restricoes_e_adultos(client):
    r=client.post("/api/churrascos",json=payload_novo())
    assert r.status_code==201, r.text
    d=r.json()
    assert d["adultos"]==10 and d["total_pessoas"]==12
    # 2 pessoas sem carne reduzem a base de carne (8 adultos + 2 crianças = 3.6 kg)
    assert d["carne_total_kg"]==pytest.approx(3.6)
    assert d["orcamento_maximo"]==300
    assert d["orcamento_status"] == "dentro"
    assert d["estimativa_precos_completa"] is True
    assert d["itens_sem_preco"] == 0
    assert d["avisos_restricoes"]


def test_usuario_logado_salva_historico_e_repetir(client):
    _,h=cadastro_login(client)
    criado=client.post("/api/churrascos",json=payload_novo(chave_cliente="hist-00000001"),headers=h)
    assert criado.status_code==201, criado.text
    cid=criado.json()["id"]
    hist=client.get("/api/churrascos/meus")
    assert hist.status_code==200 and hist.json()[0]["id"]==cid
    rep=client.post(f"/api/churrascos/{cid}/repetir",json={"adultos":8,"criancas":1},headers=h)
    assert rep.status_code==201, rep.text
    assert rep.json()["id"] != cid
    assert rep.json()["total_pessoas"]==9


def test_convite_publico_rsvp_e_aplicar(client):
    _,h=cadastro_login(client)
    c=client.post("/api/churrascos",json=payload_novo(chave_cliente="convite-0000001"),headers=h).json()
    inv=client.post(f"/api/convites/churrasco/{c['id']}",headers=h)
    assert inv.status_code==201, inv.text
    codigo=inv.json()["codigo"]
    pub=client.get(f"/api/convites/publico/{codigo}")
    assert pub.status_code==200
    for nome,tipo,veg in [("Ana","adulto",False),("Bia","adulto",True),("Leo","crianca",False)]:
        rr=client.post(f"/api/convites/publico/{codigo}/responder",json={
            "nome":nome,"resposta":"confirmado","tipo_convidado":tipo,"consome_alcool":tipo=="adulto","vegano":veg
        })
        assert rr.status_code==201, rr.text
    resumo=client.get(f"/api/convites/churrasco/{c['id']}/resumo").json()
    assert resumo["confirmados"]==3 and resumo["adultos_confirmados"]==2 and resumo["criancas_confirmadas"]==1
    apl=client.post(f"/api/convites/churrasco/{c['id']}/aplicar-confirmados",headers=h)
    assert apl.status_code==200, apl.text
    assert apl.json()["total_pessoas"]==3 and apl.json()["veganos"]==1


def test_checklist_registra_valor_real(client):
    c=client.post("/api/churrascos",json=payload_novo(chave_cliente="lista-real-00001")).json()
    lista=client.get(f"/api/lista-compras/{c['id']}").json()
    item=lista["itens"][0]
    r=client.put(f"/api/lista-compras/item/{item['id']}",json={"comprado":True,"valor_pago_total":123.45})
    assert r.status_code==200
    lista2=client.get(f"/api/lista-compras/{c['id']}").json()
    assert lista2["itens_comprados"]==1
    assert lista2["total_pago"]==pytest.approx(123.45)


def test_area_parceiro_produto_comercial_preco(client):
    _,h=cadastro_login(client)
    a=client.post("/api/parceiro/ativar",headers=h)
    assert a.status_code==200 and a.json()["papel"]=="parceiro"
    est=client.post("/api/parceiro/estabelecimentos",headers=h,json={"nome":"Mercado Teste","tipo":"supermercado"})
    assert est.status_code==201, est.text
    genericos=client.get("/api/produtos?tipo_produto=generico").json()
    pai=next(p for p in genericos if p["slug"]=="agua")
    prod=client.post("/api/parceiro/produtos",headers=h,json={
        "produto_pai_id":pai["id"],"nome":"Água Mineral 1L","marca":"Marca Teste","unidade_venda":"garrafa",
        "quantidade_embalagem":1,"unidade_embalagem":"litro"
    })
    assert prod.status_code==201, prod.text
    preco=client.post("/api/parceiro/precos",headers=h,json={
        "produto_id":prod.json()["id"],"estabelecimento_id":est.json()["id"],"preco":2.99
    })
    assert preco.status_code==201, preco.text


def test_otimizacao_requer_login_e_retorna_cestas(client):
    _,h=cadastro_login(client)
    c=client.post("/api/churrascos",json=payload_novo(chave_cliente="opt-00000000001",vegetarianos=0,veganos=0),headers=h).json()
    r=client.get(f"/api/onde-comprar/churrasco/{c['id']}?modo=preco")
    assert r.status_code==200, r.text
    d=r.json()
    assert "cestas" in d and "compra_otimizada" in d


def test_orcamento_nao_declara_dentro_quando_estimativa_e_parcial(client):
    r = client.post("/api/churrascos", json=payload_novo(
        chave_cliente="budget-parcial-0001", extras_ativos=["copos"], orcamento_maximo=1000
    ))
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["custo_total_estimado"] is not None
    assert d["estimativa_precos_completa"] is False
    assert d["itens_sem_preco"] >= 1
    assert d["orcamento_status"] == "estimativa_parcial"
    assert d["orcamento_diferenca"] is None
    # O custo por pessoa continua útil como subtotal conhecido / participantes,
    # mas `estimativa_precos_completa=False` deixa claro que é parcial.
    assert d["custo_por_pessoa"] == pytest.approx(d["custo_total_estimado"] / d["total_pessoas"], abs=0.01)
    assert "Estimativa parcial" in d["aviso_precos"]



def test_divisao_funciona_com_estimativa_parcial(client):
    criado = client.post(
        "/api/churrascos",
        json=payload_novo(
            chave_cliente="divisao-parcial-0001",
            extras_ativos=["copos"],  # sem preço na fixture -> cesta parcial
            dividir_entre=4,
        ),
    )
    assert criado.status_code == 201, criado.text
    d = criado.json()
    assert d["estimativa_precos_completa"] is False
    assert d["custo_total_estimado"] is not None
    assert d["base_divisao"] == "estimado_parcial"
    assert d["valor_por_divisao"] == pytest.approx(d["custo_total_estimado"] / 4, abs=0.01)

    alterada = client.patch(
        f"/api/churrascos/{d['id']}/divisao",
        json={"dividir_entre": 3},
    )
    assert alterada.status_code == 200, alterada.text
    out = alterada.json()
    assert out["dividir_entre"] == 3
    assert out["base_divisao"] == "estimado_parcial"
    assert out["valor_por_divisao"] == pytest.approx(out["custo_total_estimado"] / 3, abs=0.01)

def test_checklist_nao_calcula_economia_com_estimativa_ou_pagamento_incompleto(client):
    c = client.post("/api/churrascos", json=payload_novo(
        chave_cliente="lista-parcial-00001", extras_ativos=["copos"]
    )).json()
    lista = client.get(f"/api/lista-compras/{c['id']}").json()
    assert lista["estimativa_completa"] is False
    assert lista["itens_sem_preco"] >= 1

    for item in lista["itens"]:
        payload = {"comprado": True}
        # Registra preço real em todos, exceto um, para validar que o total real
        # não é fechado por acidente quando falta valor informado.
        if item["id"] != lista["itens"][0]["id"]:
            payload["valor_pago_total"] = 10
        assert client.put(f"/api/lista-compras/item/{item['id']}", json=payload).status_code == 200

    atual = client.get(f"/api/lista-compras/{c['id']}").json()
    assert atual["itens_comprados"] == atual["itens_total"]
    assert atual["valor_pago_completo"] is False
    assert atual["economia_real"] is None


def test_divisao_prioriza_valor_real_quando_checklist_esta_completo(client):
    c = client.post("/api/churrascos", json=payload_novo(
        chave_cliente="divisao-real-00001", dividir_entre=2
    )).json()
    lista = client.get(f"/api/lista-compras/{c['id']}").json()
    assert lista["estimativa_completa"] is True
    for item in lista["itens"]:
        assert client.put(
            f"/api/lista-compras/item/{item['id']}",
            json={"comprado": True, "valor_pago_total": 50},
        ).status_code == 200
    atualizado = client.get(f"/api/churrascos/{c['id']}").json()
    esperado_total = 50 * len(lista["itens"])
    assert atualizado["custo_real_completo"] is True
    assert atualizado["custo_total_real"] == pytest.approx(esperado_total)
    assert atualizado["base_divisao"] == "real"
    assert atualizado["valor_por_divisao"] == pytest.approx(esperado_total / 2)


def test_rsvp_com_mesma_chave_e_idempotente_e_editavel(client):
    _, h = cadastro_login(client)
    c = client.post(
        "/api/churrascos",
        json=payload_novo(chave_cliente="convite-idempotente-01"),
        headers=h,
    ).json()
    codigo = client.post(f"/api/convites/churrasco/{c['id']}", headers=h).json()["codigo"]
    chave = "rsvp-cliente-1234567890abcdef"

    primeira = client.post(
        f"/api/convites/publico/{codigo}/responder",
        json={
            "chave_resposta": chave,
            "nome": "Ana",
            "resposta": "talvez",
            "tipo_convidado": "adulto",
            "consome_alcool": False,
        },
    )
    assert primeira.status_code == 201, primeira.text
    assert primeira.json()["chave_resposta"] == chave

    segunda = client.post(
        f"/api/convites/publico/{codigo}/responder",
        json={
            "chave_resposta": chave,
            "nome": "Ana",
            "resposta": "confirmado",
            "tipo_convidado": "adulto",
            "consome_alcool": True,
        },
    )
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["id"] == primeira.json()["id"]

    recuperada = client.get(f"/api/convites/publico/{codigo}/resposta/{chave}")
    assert recuperada.status_code == 200, recuperada.text
    assert recuperada.json()["resposta"] == "confirmado"
    assert recuperada.json()["consome_alcool"] is True

    resumo = client.get(f"/api/convites/churrasco/{c['id']}/resumo")
    assert resumo.status_code == 200, resumo.text
    dados = resumo.json()
    assert dados["total_respostas"] == 1
    assert dados["confirmados"] == 1
    # O segredo de edição não é exposto ao organizador.
    assert dados["respostas"][0]["chave_resposta"] is None


def test_registro_nao_autentica_antes_de_verificar_email_quando_obrigatorio(client, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    r = client.post(
        "/api/auth/register",
        json={"nome": "Conta Verificada", "email": "verificar@example.com", "senha": "SenhaForte123", "aceite_termos": True, "aceite_privacidade": True},
    )
    assert r.status_code == 201, r.text
    assert "verifique" in r.json()["mensagem"].lower()
    assert client.cookies.get("churrasplan_session") is None
    assert client.get("/api/auth/me").status_code == 401

    token = r.json()["dev_verification_token"]
    assert token
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"email": "verificar@example.com", "senha": "SenhaForte123"},
    )
    assert login.status_code == 200, login.text
    assert client.get("/api/auth/me").status_code == 200



def test_config_geoapify_nao_expoe_chave_de_servidor(client, monkeypatch):
    from config import settings

    cadastro_login(client, email="maps-config@example.com")
    monkeypatch.setattr(settings, "GEOAPIFY_ENABLED", True)
    monkeypatch.setattr(settings, "GEOAPIFY_MAP_API_KEY", "map-publica-teste")
    monkeypatch.setattr(settings, "GEOAPIFY_SERVER_API_KEY", "server-secreta-teste")

    r = client.get("/api/onde-comprar/config")
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados == {
        "geoapify_map_disponivel": True,
        "geoapify_places_disponivel": True,
        "geoapify_map_api_key": "map-publica-teste",
    }
    assert "server-secreta-teste" not in r.text



def test_onde_comprar_post_nao_coloca_localizacao_na_url(client, monkeypatch):
    from config import settings

    _, h = cadastro_login(client, email="maps-post@example.com")
    monkeypatch.setattr(settings, "GEOAPIFY_ENABLED", False)
    c = client.post(
        "/api/churrascos",
        json=payload_novo(chave_cliente="maps-post-0000001", vegetarianos=0, veganos=0),
        headers=h,
    )
    assert c.status_code == 201, c.text
    cid = c.json()["id"]

    proximos = client.post(
        "/api/onde-comprar/proximos",
        json={"latitude": -19.9, "longitude": -43.9, "raio_km": 15},
        headers=h,
    )
    assert proximos.status_code == 200, proximos.text
    assert isinstance(proximos.json(), list)

    otim = client.post(
        f"/api/onde-comprar/churrasco/{cid}",
        json={"modo": "equilibrio", "latitude": -19.9, "longitude": -43.9},
        headers=h,
    )
    assert otim.status_code == 200, otim.text
    assert otim.json()["churrasco_id"] == cid

def test_geoapify_places_e_autocomplete(monkeypatch):
    import json
    from config import settings
    from services import geoapify

    monkeypatch.setattr(settings, "GEOAPIFY_ENABLED", True)
    monkeypatch.setattr(settings, "GEOAPIFY_SERVER_API_KEY", "server-key-teste")

    respostas = [
        {
            "features": [
                {
                    "properties": {
                        "place_id": "mercado-1",
                        "name": "Mercado Aberto",
                        "formatted": "Rua Teste, 1",
                        "categories": ["commercial.supermarket"],
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-43.9, -19.9],
                    },
                }
            ]
        },
        {
            "results": [
                {
                    "place_id": "endereco-1",
                    "formatted": "Rua Teste, 1, Belo Horizonte",
                    "lat": -19.9,
                    "lon": -43.9,
                }
            ]
        },
    ]

    class Resposta:
        def __init__(self, payload):
            self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(*args, **kwargs):
        return Resposta(respostas.pop(0))

    monkeypatch.setattr(geoapify.urllib.request, "urlopen", fake_urlopen)

    proximos = geoapify.buscar_proximos(-19.9, -43.9)
    assert proximos[0]["provider_place_id"] == "mercado-1"
    assert proximos[0]["nome"] == "Mercado Aberto"

    enderecos = geoapify.autocomplete_enderecos("Rua Teste")
    assert enderecos[0]["place_id"] == "endereco-1"
    assert enderecos[0]["label"] == "Rua Teste, 1, Belo Horizonte"


def test_validacao_de_producao_recusa_configuracao_insegura():
    from types import SimpleNamespace
    from config import validar_configuracao_producao
    cfg = SimpleNamespace(
        APP_ENV="production", COOKIE_SECURE=False, REQUIRE_EMAIL_VERIFICATION=True,
        SMTP_HOST=None, PUBLIC_APP_URL="http://exemplo.com", CORS_ORIGINS=["*"],
        GEOAPIFY_ENABLED=True, GEOAPIFY_SERVER_API_KEY=None, GEOAPIFY_MAP_API_KEY=None,
        TRUSTED_HOSTS=["*"], SECURITY_PEPPER="curto", FORCE_HTTPS=False,
        DATABASE_URL="sqlite:///inseguro.db", DATABASE_URL_OVERRIDE="sqlite:///inseguro.db", DB_PASSWORD="",
    )
    with pytest.raises(RuntimeError) as exc:
        validar_configuracao_producao(cfg)
    texto = str(exc.value)
    assert "COOKIE_SECURE" in texto and "SMTP_HOST" in texto and "HTTPS" in texto and "CORS_ORIGINS" in texto


def test_oferta_de_parceiro_nao_verificado_nao_entra_em_preco_publico_ou_orcamento(client):
    _, h = cadastro_login(client, email="parceiro-preco@example.com")
    assert client.post("/api/parceiro/ativar", headers=h).status_code == 200
    est = client.post(
        "/api/parceiro/estabelecimentos", headers=h,
        json={"nome": "Loja Ainda Não Verificada", "tipo": "supermercado"},
    )
    assert est.status_code == 201, est.text
    picanha = next(p for p in client.get("/api/produtos?tipo_produto=generico").json() if p["slug"] == "picanha")
    preco = client.post(
        "/api/parceiro/precos", headers=h,
        json={"produto_id": picanha["id"], "estabelecimento_id": est.json()["id"], "preco": 0.01},
    )
    assert preco.status_code == 201, preco.text

    comparar = client.get(f"/api/precos/comparar?produto_id={picanha['id']}")
    assert comparar.status_code == 200
    assert all(item["origem"] != "manual_parceiro" for item in comparar.json())
    historico_publico = client.get(f"/api/precos?produto_id={picanha['id']}")
    assert historico_publico.status_code == 200
    assert all(item["origem"] != "manual_parceiro" for item in historico_publico.json())
    resumo_preco = client.get(f"/api/precos/resumo/{picanha['id']}").json()
    assert resumo_preco["preco_minimo_atual"] != pytest.approx(0.01)

    churrasco = client.post(
        "/api/churrascos",
        json=payload_novo(chave_cliente="preco-verificado-0001", vegetarianos=0, veganos=0),
        headers=h,
    )
    assert churrasco.status_code == 201, churrasco.text
    item = next(i for i in churrasco.json()["itens"] if i["produto_slug"] == "picanha")
    assert item["preco_estimado"] != pytest.approx(0.01)


def test_metricas_parceiro_registram_visualizacao_e_clique_sem_identificador_pessoal(client):
    _, h_parceiro = cadastro_login(client, email="parceiro-metricas@example.com")
    assert client.post("/api/parceiro/ativar", headers=h_parceiro).status_code == 200
    est = client.post(
        "/api/parceiro/estabelecimentos", headers=h_parceiro,
        json={"nome": "Mercado Métricas", "tipo": "supermercado", "latitude": -19.95, "longitude": -43.85},
    )
    assert est.status_code == 201, est.text
    est_id = est.json()["id"]

    # Outra conta representa o usuário que está planejando/comprando.
    assert client.post("/api/auth/logout", headers=h_parceiro).status_code == 200
    _, h_usuario = cadastro_login(client, email="usuario-metricas@example.com")
    churrasco = client.post(
        "/api/churrascos",
        json=payload_novo(chave_cliente="metricas-usuario-0001", vegetarianos=0, veganos=0),
        headers=h_usuario,
    )
    assert churrasco.status_code == 201, churrasco.text
    cid = churrasco.json()["id"]

    for tipo, contexto in [("visualizacao", "onde_comprar"), ("clique", "rota")]:
        r = client.post(
            "/api/onde-comprar/interacoes",
            headers=h_usuario,
            json={
                "tipo": tipo,
                "estabelecimento_ids": [est_id],
                "churrasco_id": cid,
                "contexto": contexto,
            },
        )
        assert r.status_code == 204, r.text

    assert client.post("/api/auth/logout", headers=h_usuario).status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"email": "parceiro-metricas@example.com", "senha": "SenhaForte123"},
    )
    assert login.status_code == 200, login.text
    csrf = client.cookies.get("churrasplan_csrf")
    dash = client.get("/api/parceiro/dashboard", headers={"X-CSRF-Token": csrf}).json()
    assert dash["visualizacoes"] == 1
    assert dash["cliques"] == 1

    # O modelo não possui campos de identificação pessoal para a métrica.
    from models import MetricaEstabelecimento
    colunas = set(MetricaEstabelecimento.__table__.columns.keys())
    assert colunas == {"id", "estabelecimento_id", "tipo", "contexto", "criado_em"}
    assert "usuario_id" not in colunas and "churrasco_id" not in colunas and "ip" not in colunas and "latitude" not in colunas
