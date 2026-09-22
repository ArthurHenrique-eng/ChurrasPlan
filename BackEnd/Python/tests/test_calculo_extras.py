import pytest
from services import calculo_extras


def test_copos_com_margem():
    r=calculo_extras.calcular_extras(14,5,["copos"])
    assert r["copos_unidades"] == 31  # 14*2*1.10=30.8


def test_extra_desativado_nao_aparece():
    assert "pratos_unidades" not in calculo_extras.calcular_extras(14,5,["copos"])


def test_sal_grosso_depende_da_carne():
    assert calculo_extras.calcular_extras(100,10,["sal_grosso"])["sal_grosso_kg"] == pytest.approx(.2)


def test_farofa_por_pessoa():
    assert calculo_extras.calcular_acompanhamentos(14,["farofa"])["farofa_kg"] == pytest.approx(.84)


def test_pao_de_alho_arredonda():
    assert calculo_extras.calcular_acompanhamentos(15,["pao_de_alho"])["pao_de_alho_unidades"] == 12
