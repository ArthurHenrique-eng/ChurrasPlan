import pytest
from services import calculo_bebidas


def test_cerveja_usa_somente_consumidores_adultos_informados():
    r = calculo_bebidas.calcular_bebida_alcoolica(5,4,"normal",tipo_evento="almoco")
    assert r["litros_total"] == pytest.approx(5*.45*4)


def test_ninguem_bebe_alcool():
    assert calculo_bebidas.calcular_bebida_alcoolica(0,4,"normal")["litros_total"] == 0


def test_cerveja_personalizada():
    r = calculo_bebidas.calcular_bebida_alcoolica(2,4,"personalizado",{"cerveja_litros_consumidor_hora":.3},"almoco")
    assert r["litros_total"] == pytest.approx(2.4)


def test_nao_alcoolicas_por_evento_e_perfil():
    r = calculo_bebidas.calcular_bebidas_nao_alcoolicas(14,"normal",["agua","refrigerante"],tipo_evento="almoco")
    assert r["agua"] == pytest.approx(10.5)
    assert r["refrigerante"] == pytest.approx(7.0)


def test_bebida_desativada_nao_aparece():
    r=calculo_bebidas.calcular_bebidas_nao_alcoolicas(14,"normal",["agua"])
    assert "refrigerante" not in r


def test_evento_prolongado_afeta_bebida_sem_duplicar_duracao():
    base=calculo_bebidas.calcular_bebidas_nao_alcoolicas(10,"normal",["agua"],tipo_evento="almoco")["agua"]
    pro=calculo_bebidas.calcular_bebidas_nao_alcoolicas(10,"normal",["agua"],tipo_evento="evento_prolongado")["agua"]
    assert pro == pytest.approx(base*1.10)


def test_gelo_desativado_e_zero():
    assert calculo_bebidas.calcular_gelo(14,4,"normal",gelo_ativo=False) == 0


@pytest.mark.parametrize("duracao,fator",[(2,.8),(3,.8),(4,1),(5,1),(6,1.2),(7,1.2),(8,1.4)])
def test_gelo_faixas_quando_ativo(duracao,fator):
    gelo=calculo_bebidas.calcular_gelo(14,duracao,"normal",gelo_ativo=True)
    assert gelo == pytest.approx(14*.5*fator)


def test_conversao_cerveja_respeita_embalagem_do_catalogo():
    produto, compra=calculo_bebidas.converter_bebida_para_compra("cerveja",9.0)
    assert produto.unidade_venda == "lata"
    assert compra.embalagens == 26
    assert compra.compra == pytest.approx(9.1)
