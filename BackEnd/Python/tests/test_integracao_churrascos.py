from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from main import app
from models import Categoria, Estabelecimento, Preco, Produto


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db = Session()
    cats = {}
    for nome, tipo in [("Carnes","carne"),("Bebidas","bebida"),("Extras","extra"),("Acompanhamentos","acompanhamento")]:
        c=Categoria(nome=nome,tipo=tipo); db.add(c); db.flush(); cats[tipo]=c

    def produto(slug,nome,categoria,uc,uv,fracionada=False,inc=None,emb=None,ue=None):
        p=Produto(categoria_id=cats[categoria].id,slug=slug,nome=nome,unidade_consumo=uc,unidade_venda=uv,
                  venda_fracionada=fracionada,incremento_venda=inc,quantidade_embalagem=emb,unidade_embalagem=ue,ativo=True)
        db.add(p); db.flush(); return p

    produtos={
        "picanha":produto("picanha","Picanha","carne","kg","kg",True,.1),
        "alcatra":produto("alcatra","Alcatra","carne","kg","kg",True,.1),
        "carvao":produto("carvao","Carvão","extra","kg","saco",False,None,3,"kg"),
        "agua":produto("agua","Água","bebida","litro","garrafa",False,None,1.5,"litro"),
        "cerveja":produto("cerveja","Cerveja","bebida","litro","lata",False,None,.35,"litro"),
        "gelo":produto("gelo","Gelo","bebida","kg","saco",False,None,5,"kg"),
    }
    a=Estabelecimento(slug="mercado-a",nome="Mercado A",tipo="supermercado",ativo=True)
    b=Estabelecimento(slug="mercado-b",nome="Mercado B",tipo="supermercado",ativo=True)
    db.add_all([a,b]); db.flush()
    # Picanha: oferta antiga de A era mais barata, mas a atual de A é 55. B atual é 50.
    db.add_all([
        Preco(produto_id=produtos["picanha"].id,estabelecimento_id=a.id,preco=40,fonte="hist",data_atualizacao=datetime(2026,1,1),coletado_em=datetime(2026,1,1)),
        Preco(produto_id=produtos["picanha"].id,estabelecimento_id=a.id,preco=55,fonte="atual",data_atualizacao=datetime(2026,9,1),coletado_em=datetime(2026,9,1)),
        Preco(produto_id=produtos["picanha"].id,estabelecimento_id=b.id,preco=50,fonte="atual",data_atualizacao=datetime(2026,8,30),coletado_em=datetime(2026,8,30)),
        Preco(produto_id=produtos["carvao"].id,estabelecimento_id=a.id,preco=18,fonte="atual"),
        Preco(produto_id=produtos["agua"].id,estabelecimento_id=a.id,preco=3.5,fonte="atual"),
        Preco(produto_id=produtos["cerveja"].id,estabelecimento_id=a.id,preco=4.5,fonte="atual"),
        Preco(produto_id=produtos["gelo"].id,estabelecimento_id=a.id,preco=14,fonte="atual"),
    ])
    db.commit(); db.close()
    yield TestClient(app)
    app.dependency_overrides.clear()


def payload(**overrides):
    p={
        "chave_cliente":"planejamento-teste-0001",
        "tipo_evento":"almoco","duracao_horas":4,"perfil_consumo":"normal",
        "homens":6,"mulheres":5,"criancas":3,"homens_bebem_alcool":3,"mulheres_bebem_alcool":2,
        "carnes":[{"nome":"Picanha","produto_slug":"picanha","percentual":100}],
        "carvao_ativo":True,"bebidas_nao_alcoolicas_ativas":["agua"],"bebida_alcoolica_ativa":True,
        "gelo_ativo":False,"extras_ativos":[],"acompanhamentos_ativos":[],
    }
    p.update(overrides); return p


def test_fluxo_calcula_necessidade_compra_e_custo_real(client):
    r=client.post("/api/churrascos",json=payload())
    assert r.status_code==201
    d=r.json()
    assert d["carne_total_kg"]==pytest.approx(5.0)
    picanha=next(i for i in d["itens"] if i["produto_slug"]=="picanha")
    assert picanha["quantidade_necessaria"]==pytest.approx(5)
    assert picanha["quantidade_compra"]==pytest.approx(5)
    assert picanha["preco_estimado"]==pytest.approx(50)  # ignora oferta histórica vencida de 40
    assert picanha["estabelecimento_nome"]=="Mercado B"
    assert picanha["subtotal_estimado"]==pytest.approx(250)
    carvao=next(i for i in d["itens"] if i["produto_slug"]=="carvao")
    assert carvao["quantidade_necessaria"]==pytest.approx(2.5)
    assert carvao["quantidade_compra"]==pytest.approx(3)
    assert carvao["quantidade_embalagens"]==1
    assert carvao["subtotal_estimado"]==pytest.approx(18)
    assert d["carvao_necessario_kg"]==pytest.approx(2.5)
    assert d["carvao_compra_kg"]==pytest.approx(3)


def test_custo_total_usa_compra_e_nao_necessidade(client):
    d=client.post("/api/churrascos",json=payload(bebidas_nao_alcoolicas_ativas=[],bebida_alcoolica_ativa=False)).json()
    # 5kg picanha * R$50 + 1 saco de carvão * R$18
    assert d["custo_total_estimado"]==pytest.approx(268)


def test_lista_de_compras_usa_quantidade_compra(client):
    d=client.post("/api/churrascos",json=payload(bebidas_nao_alcoolicas_ativas=[],bebida_alcoolica_ativa=False)).json()
    lista=client.get(f"/api/lista-compras/{d['id']}").json()
    carvao=next(i for i in lista["itens"] if i["descricao"]=="Carvão")
    assert carvao["quantidade"]==pytest.approx(3)
    assert carvao["quantidade_embalagens"]==1
    assert carvao["unidade_venda"]=="saco"
    assert carvao["subtotal_estimado"]==pytest.approx(18)


def test_post_e_get_possuem_mesma_semantica(client):
    post=client.post("/api/churrascos",json=payload()).json()
    get=client.get(f"/api/churrascos/{post['id']}").json()
    def normalizar(d):
        return sorted([(i["produto_slug"],i["quantidade_necessaria"],i["quantidade_compra"],i["unidade_necessaria"],i["unidade_compra"],i["subtotal_estimado"]) for i in d["itens"]])
    assert normalizar(post)==normalizar(get)
    assert post["custo_total_estimado"]==get["custo_total_estimado"]


def test_chave_cliente_torna_post_idempotente(client):
    a=client.post("/api/churrascos",json=payload()).json()
    b=client.post("/api/churrascos",json=payload()).json()
    assert a["id"]==b["id"]


def test_carvao_personalizado_aplica_coeficiente(client):
    d=client.post("/api/churrascos",json=payload(
        perfil_consumo="personalizado",
        perfil_personalizado={"carne_adulto_kg":.4,"carne_crianca_kg":.2,"carvao_kg_por_kg_carne":1.0},
        bebidas_nao_alcoolicas_ativas=[],bebida_alcoolica_ativa=False,
    )).json()
    carvao=next(i for i in d["itens"] if i["produto_slug"]=="carvao")
    assert carvao["quantidade_necessaria"]==pytest.approx(5)
    assert carvao["quantidade_compra"]==pytest.approx(6)


def test_gelo_nao_entra_sem_selecao_explicita(client):
    d=client.post("/api/churrascos",json=payload(gelo_ativo=False)).json()
    assert "gelo" not in [i["produto_slug"] for i in d["itens"]]


def test_gelo_ativo_entra_com_embalagem(client):
    d=client.post("/api/churrascos",json=payload(gelo_ativo=True)).json()
    gelo=next(i for i in d["itens"] if i["produto_slug"]=="gelo")
    assert gelo["quantidade_necessaria"]==pytest.approx(7)
    assert gelo["quantidade_compra"]==pytest.approx(10)
    assert gelo["quantidade_embalagens"]==2


def test_cerveja_nao_mistura_litros_com_latas(client):
    d=client.post("/api/churrascos",json=payload()).json()
    cerveja=next(i for i in d["itens"] if i["produto_slug"]=="cerveja")
    assert cerveja["unidade_necessaria"]=="litro"
    assert cerveja["quantidade_necessaria"]==pytest.approx(9)
    assert cerveja["quantidade_embalagens"]==26
    assert cerveja["unidade_venda"]=="lata"
    assert cerveja["quantidade_compra"]==pytest.approx(9.1)


def test_carvao_desativado(client):
    d=client.post("/api/churrascos",json=payload(carvao_ativo=False)).json()
    assert d["carvao_ativo"] is False
    assert d["carvao_necessario_kg"]==0
    assert d["carvao_compra_kg"]==0
    assert "carvao" not in [i["produto_slug"] for i in d["itens"]]


def test_put_recalcula_sem_duplicar(client):
    criado=client.post("/api/churrascos",json=payload()).json()
    atualizado=client.put(f"/api/churrascos/{criado['id']}",json=payload(carvao_ativo=False)).json()
    assert atualizado["id"]==criado["id"]
    assert "carvao" not in [i["produto_slug"] for i in atualizado["itens"]]


def test_total_de_convidados_maior_500_rejeitado(client):
    r=client.post("/api/churrascos",json=payload(homens=300,mulheres=201,criancas=0,homens_bebem_alcool=0,mulheres_bebem_alcool=0))
    assert r.status_code==422


def test_percentual_invalido_rejeitado(client):
    r=client.post("/api/churrascos",json=payload(carnes=[{"nome":"Picanha","produto_slug":"picanha","percentual":80}]))
    assert r.status_code==422


def test_alcool_maior_que_adultos_rejeitado(client):
    assert client.post("/api/churrascos",json=payload(homens=2,homens_bebem_alcool=3)).status_code==422


def test_lista_pode_marcar_comprado(client):
    d=client.post("/api/churrascos",json=payload()).json()
    lista=client.get(f"/api/lista-compras/{d['id']}").json()
    item=lista["itens"][0]
    assert client.put(f"/api/lista-compras/item/{item['id']}",json={"comprado":True}).status_code==200
    atualizado=client.get(f"/api/lista-compras/{d['id']}").json()
    assert next(x for x in atualizado["itens"] if x["id"]==item["id"])["comprado"] is True
