import pytest
from services import calculo_carne


def test_exemplo_home_11_adultos_3_criancas_4h_almoco_normal():
    r = calculo_carne.calcular_quantidade_total_carne(6, 5, 3, 4, "normal", tipo_evento="almoco")
    assert r["total_kg"] == pytest.approx(5.0, abs=0.001)
    assert r["adultos"] == 11
    assert r["criancas"] == 3


def test_1_adulto_normal_4h():
    assert calculo_carne.calcular_quantidade_total_carne(1, 0, 0, 4, "normal")["total_kg"] == pytest.approx(0.4)


def test_apenas_criancas():
    assert calculo_carne.calcular_quantidade_total_carne(0, 0, 4, 4, "normal")["total_kg"] == pytest.approx(0.8)


@pytest.mark.parametrize("duracao,fator", [(2,.9),(3,.9),(3.5,1),(5,1),(6,1.1),(7,1.1),(8,1.2),(9,1.2),(10,1.3),(24,1.3)])
def test_faixas_duracao(duracao, fator):
    r = calculo_carne.calcular_quantidade_total_carne(10,0,0,duracao,"normal")
    assert r["fator_duracao"] == pytest.approx(fator)


def test_perfis_aplicados_uma_vez():
    normal = calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"normal")["total_kg"]
    assert calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"leve")["total_kg"] == pytest.approx(normal*.85)
    assert calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"alto")["total_kg"] == pytest.approx(normal*1.2)


def test_tipo_evento_e_funcional():
    almoco = calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"normal",tipo_evento="almoco")["total_kg"]
    prolongado = calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"normal",tipo_evento="evento_prolongado")["total_kg"]
    assert prolongado == pytest.approx(almoco*1.10)


def test_personalizado_substitui_base():
    r = calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"personalizado",{"carne_adulto_kg":.5},"almoco")
    assert r["total_kg"] == pytest.approx(5.0)


def test_personalizado_sem_parametros_falha():
    with pytest.raises(ValueError, match="personalizado"):
        calculo_carne.calcular_quantidade_total_carne(10,0,0,4,"personalizado")


def test_distribuicao_percentual_e_venda_fracionada():
    itens = calculo_carne.distribuir_carnes(5.0, [
        {"nome":"Picanha","produto_slug":"picanha","percentual":40},
        {"nome":"Alcatra","produto_slug":"alcatra","percentual":60},
    ])
    assert itens[0]["quantidade_kg"] == pytest.approx(2.0)
    assert itens[0]["quantidade_compra_kg"] == pytest.approx(2.0)
    assert itens[0]["quantidade_embalagens"] is None
    assert sum(i["quantidade_kg"] for i in itens) == pytest.approx(5.0)


def test_distribuicao_nao_forca_pacote_global_de_2kg():
    item = calculo_carne.distribuir_carnes(1.83,[{"nome":"Picanha","produto_slug":"picanha","percentual":100}])[0]
    assert item["quantidade_compra_kg"] == pytest.approx(1.9)  # incremento comercial de 100g
    assert item["quantidade_compra_kg"] != 2.0


def test_percentual_invalido_falha():
    with pytest.raises(ValueError, match="100%"):
        calculo_carne.distribuir_carnes(5,[{"nome":"Picanha","percentual":90}])


def test_carvao_padrao_e_embalagem():
    carvao = calculo_carne.calcular_carvao(5.0,4,True)
    assert carvao["necessario_kg"] == pytest.approx(2.5)
    assert carvao["compra_kg"] == pytest.approx(3.0)
    assert carvao["sacos"] == 1


def test_carvao_personalizado_realmente_altera_coeficiente():
    carvao = calculo_carne.calcular_carvao(5.0,4,True,{"carvao_kg_por_kg_carne":1.0},"personalizado")
    assert carvao["necessario_kg"] == pytest.approx(5.0)
    assert carvao["compra_kg"] == pytest.approx(6.0)
    assert carvao["sacos"] == 2


def test_carvao_desativado_zera():
    assert calculo_carne.calcular_carvao(5,4,False)["compra_kg"] == 0
