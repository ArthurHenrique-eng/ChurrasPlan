"""Contrato de coordenadas para parceiros e administradores."""
import pytest
from pydantic import ValidationError

from schemas.estabelecimento import EstabelecimentoParceiroCreate


@pytest.mark.parametrize(
    "latitude, longitude",
    [
        (-19.959383, -44.01187),
        ("-19,959383", "-44,011870"),
        ("-19.959383", "-44.011870"),
        (0, 0),
        (-90, 180),
        (90, -180),
    ],
)
def test_aceita_graus_decimais(latitude, longitude):
    local = EstabelecimentoParceiroCreate(
        nome="Mercado de teste", latitude=latitude, longitude=longitude
    )
    assert local.latitude == pytest.approx(float(str(latitude).replace(",", ".")))
    assert local.longitude == pytest.approx(float(str(longitude).replace(",", ".")))


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (-19959383, -44011870),
        (91, -44),
        (-19, -181),
        ("NaN", "-44"),
        ("inf", "-44"),
        ("-19,95.9", "-44"),
        (True, -44),
        ("coordenada", "-44"),
    ],
)
def test_recusa_coordenadas_invalidas_sem_corrigir_por_divisao(latitude, longitude):
    with pytest.raises(ValidationError):
        EstabelecimentoParceiroCreate(
            nome="Mercado de teste", latitude=latitude, longitude=longitude
        )


def test_aceita_omissao_de_coordenadas():
    local = EstabelecimentoParceiroCreate(nome="Mercado sem geocodificação")
    assert local.latitude is None
    assert local.longitude is None
