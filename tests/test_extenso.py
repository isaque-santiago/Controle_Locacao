"""Testes de src/domain/extenso.py."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.extenso import data_por_extenso, inteiro_por_extenso, moeda_por_extenso


@pytest.mark.parametrize(
    "numero, esperado",
    [
        (0, "zero"),
        (1, "um"),
        (15, "quinze"),
        (21, "vinte e um"),
        (100, "cem"),
        (101, "cento e um"),
        (280, "duzentos e oitenta"),
        (999, "novecentos e noventa e nove"),
        (1000, "mil"),
        (1050, "mil e cinquenta"),
        (1200, "mil e duzentos"),
        (1250, "mil duzentos e cinquenta"),
        (2001, "dois mil e um"),
        (10000, "dez mil"),
        (1_000_000, "um milhão"),
        (1_000_001, "um milhão e um"),
        (2_500_000, "dois milhões e quinhentos mil"),
    ],
)
def test_inteiro_por_extenso(numero, esperado):
    assert inteiro_por_extenso(numero) == esperado


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (0, "zero real"),
        (1, "um real"),
        (280, "duzentos e oitenta reais"),
        (500, "quinhentos reais"),
        (10000, "dez mil reais"),
        (Decimal("15.00"), "quinze reais"),
        (Decimal("1.50"), "um real e cinquenta centavos"),
        (Decimal("0.01"), "um centavo"),
        (Decimal("20.5"), "vinte reais e cinquenta centavos"),
        (1_000_000, "um milhão de reais"),
        ("400", "quatrocentos reais"),
    ],
)
def test_moeda_por_extenso(valor, esperado):
    assert moeda_por_extenso(valor) == esperado


def test_moeda_arredonda_para_centavos():
    assert moeda_por_extenso(Decimal("1.999")) == "dois reais"


def test_moeda_negativa_e_recusada():
    with pytest.raises(ValueError):
        moeda_por_extenso(-1)


def test_inteiro_fora_do_intervalo_e_recusado():
    with pytest.raises(ValueError):
        inteiro_por_extenso(10**12)


def test_data_por_extenso():
    assert data_por_extenso(date(2026, 2, 11)) == "11 de fevereiro de 2026"
    assert data_por_extenso(date(2026, 3, 5)) == "05 de março de 2026"
