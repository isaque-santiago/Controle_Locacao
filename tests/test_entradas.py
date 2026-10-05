"""Entrada de dados dos formulários: máscaras, normalização e mensagens de validação."""

import re
from decimal import Decimal

import pytest

from src.domain.entradas import (
    REGEX_CPF,
    REGEX_MOEDA,
    REGEX_PLACA,
    REGEX_TELEFONE,
    decimal_campo,
    erro_de,
    formatar_cpf,
    formatar_telefone,
    inteiro_campo,
    normalizar_placa,
    primeiro_erro,
    texto_moeda,
    texto_percentual,
    texto_placa,
)


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (None, "0,00"),
        ("", "0,00"),
        (0, "0,00"),
        ("380.00", "380,00"),
        (Decimal("1234.5"), "1.234,50"),
        (1234567.891, "1.234.567,89"),
        ("texto", "0,00"),
    ],
)
def test_texto_moeda_usa_o_padrao_brasileiro(valor, esperado):
    assert texto_moeda(valor) == esperado


def test_texto_percentual_nao_usa_separador_de_milhar():
    assert texto_percentual(2) == "2,00"
    assert texto_percentual(Decimal("1.5")) == "1,50"


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("1.234,56", Decimal("1234.56")),
        ("1234,56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("R$ 380,00", Decimal("380.00")),
        ("1.500", Decimal("1500.00")),
        ("2.000.000", Decimal("2000000.00")),
        ("0", Decimal("0.00")),
        ("  12,5 ", Decimal("12.50")),
    ],
)
def test_decimal_campo_aceita_formatos_brasileiros(texto, esperado):
    assert decimal_campo(texto, "Valor") == esperado


@pytest.mark.parametrize(
    "texto, trecho",
    [
        ("", "informe um valor"),
        ("   ", "informe um valor"),
        ("abc", "só números"),
        ("1,2,3", "só números"),
        ("-5", "negativo"),
        ("10,999", "duas casas"),
        ("10.5555", "duas casas"),
    ],
)
def test_decimal_campo_nomeia_o_campo_e_diz_como_corrigir(texto, trecho):
    with pytest.raises(ValueError) as erro:
        decimal_campo(texto, "Caução")
    assert str(erro.value).startswith("Caução:")
    assert trecho in str(erro.value)


def test_decimal_campo_positivo_recusa_zero():
    with pytest.raises(ValueError, match="maior que zero"):
        decimal_campo("0,00", "Valor do período", positivo=True)
    assert decimal_campo("0,01", "Valor do período", positivo=True) == Decimal("0.01")


def test_texto_moeda_volta_para_decimal_campo_sem_perder_centavos():
    for valor in ("0.01", "999.99", "1234567.89"):
        assert decimal_campo(texto_moeda(valor), "Valor") == Decimal(valor)


def test_inteiro_campo():
    assert inteiro_campo(" 30 ", "Carência (dias)") == 30
    with pytest.raises(ValueError, match="Carência"):
        inteiro_campo("3,5", "Carência (dias)")
    with pytest.raises(ValueError, match="menor valor aceito é 1"):
        inteiro_campo("0", "Quantidade", minimo=1)
    with pytest.raises(ValueError, match="maior valor aceito é 365"):
        inteiro_campo("400", "Dias", maximo=365)


def test_cpf_e_telefone_ganham_mascara_so_quando_completos():
    assert formatar_cpf("52998224725") == "529.982.247-25"
    assert formatar_cpf("529.982.247-25") == "529.982.247-25"
    assert formatar_cpf(" 5299822 ") == "5299822"
    assert formatar_telefone("11912345678") == "(11) 91234-5678"
    assert formatar_telefone("1134567890") == "(11) 3456-7890"
    assert formatar_telefone("12345") == "12345"
    assert formatar_cpf(None) == "" and formatar_telefone(None) == ""


def test_placa_normaliza_para_o_formato_do_banco_e_exibe_com_hifen():
    assert normalizar_placa(" abc-1d23 ") == "ABC1D23"
    assert texto_placa("abc1d23") == "ABC-1D23"
    assert texto_placa("ab") == "AB"


def test_erro_de_e_primeiro_erro():
    assert erro_de(decimal_campo, "10,00", "Valor") is None
    assert erro_de(decimal_campo, "x", "Valor").startswith("Valor:")
    assert primeiro_erro(None, "", "B", "C") == "B"
    assert primeiro_erro(None, None) is None


@pytest.mark.parametrize("texto", ["1.234,56", "1234,56", "1234.56", "1.500", "R$ 10", "0", "12,5"])
def test_regex_de_moeda_aceita_o_que_decimal_campo_aceita(texto):
    assert re.search(REGEX_MOEDA, texto)
    decimal_campo(texto, "Valor")


@pytest.mark.parametrize("texto", ["", "abc", "1,234,5", "10,999", "1.23.4"])
def test_regex_de_moeda_recusa_entradas_que_decimal_campo_recusa(texto):
    assert texto == "" or not re.search(REGEX_MOEDA, texto)


def test_regex_de_cpf_telefone_e_placa():
    assert re.search(REGEX_CPF, "529.982.247-25") and re.search(REGEX_CPF, "52998224725")
    assert not re.search(REGEX_CPF, "529.982.247")
    assert re.search(REGEX_TELEFONE, "(11) 91234-5678") and re.search(REGEX_TELEFONE, "1134567890")
    assert not re.search(REGEX_TELEFONE, "12345")
    assert re.search(REGEX_PLACA, "ABC-1D23") and re.search(REGEX_PLACA, "abc1234")
    assert not re.search(REGEX_PLACA, "AB12345")
