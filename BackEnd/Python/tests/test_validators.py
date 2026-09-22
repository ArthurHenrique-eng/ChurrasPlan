"""Testes de utils/validators.py."""
import pytest

from utils.validators import (
    validar_soma_percentuais, validar_nao_negativo, validar_perfil_personalizado,
)


def test_soma_percentuais_valida():
    validar_soma_percentuais([{"percentual": 40}, {"percentual": 30}, {"percentual": 30}])


def test_soma_percentuais_invalida():
    with pytest.raises(ValueError, match="100%"):
        validar_soma_percentuais([{"percentual": 40}, {"percentual": 30}, {"percentual": 20}])


def test_nao_negativo_aceita_positivo():
    validar_nao_negativo(5, "quantidade")


def test_nao_negativo_rejeita_negativo():
    with pytest.raises(ValueError, match="não pode ser negativo"):
        validar_nao_negativo(-1, "quantidade")


def test_perfil_personalizado_ok():
    validar_perfil_personalizado("personalizado", {"carne_adulto_kg": 2.0})


def test_perfil_personalizado_ignora_outros_perfis():
    validar_perfil_personalizado("normal", None)  # nao deve levantar erro


def test_perfil_personalizado_sem_coeficientes_falha():
    with pytest.raises(ValueError, match="personalizado"):
        validar_perfil_personalizado("personalizado", None)


def test_perfil_personalizado_chave_desconhecida_falha():
    with pytest.raises(ValueError, match="desconhecido"):
        validar_perfil_personalizado("personalizado", {"chave_invalida": 1})


def test_perfil_personalizado_valor_negativo_falha():
    with pytest.raises(ValueError, match="não-negativo"):
        validar_perfil_personalizado("personalizado", {"carne_adulto_kg": -1})
