"""Testes de src/domain/numero_whatsapp.py: normalização para 55 + DDD + número."""

import pytest

from src.domain.numero_whatsapp import normalizar_numero


@pytest.mark.parametrize("texto, esperado", [
    ("(11) 98888-7777", "5511988887777"),
    ("11988887777", "5511988887777"),
    ("011 98888-7777", "5511988887777"),
    ("+55 11 98888-7777", "5511988887777"),
    ("55 (11) 98888-7777", "5511988887777"),
    ("  (21) 9 7777-6666 ", "5521977776666"),
    ("(11) 8888-7777", "551188887777"),  # celular antigo de 8 dígitos (começa com 6 a 9)
])
def test_numeros_validos(texto, esperado):
    assert normalizar_numero(texto) == esperado


@pytest.mark.parametrize("texto", [
    None, "", "   ", "abc", "123", "(11) 3333-4444",       # fixo
    "(11) 88888-7777",                                      # 9 dígitos sem começar com 9
    "(05) 8888-7777", "(10) 98888-7777",                     # DDD inexistente
    "5511988887777999",                                     # comprido demais
])
def test_numeros_invalidos(texto):
    assert normalizar_numero(texto) is None


def test_resultado_combina_com_a_regra_do_banco():
    import re
    assert re.fullmatch(r"55[0-9]{10,11}", normalizar_numero("(11) 98888-7777"))
