"""Testes de src/domain/feriados.py: feriados nacionais fixos e os que dependem da Páscoa."""

from datetime import date

import pytest

from src.domain.feriados import eh_feriado, feriados_nacionais


def test_feriados_moveis_de_2026():
    # Páscoa de 2026: 5 de abril.
    f = feriados_nacionais(2026)
    assert date(2026, 2, 16) in f and date(2026, 2, 17) in f  # Carnaval
    assert f[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert f[date(2026, 6, 4)] == "Corpus Christi"


def test_feriados_moveis_de_2027():
    # Páscoa de 2027: 28 de março.
    f = feriados_nacionais(2027)
    assert date(2027, 2, 8) in f and date(2027, 2, 9) in f
    assert date(2027, 3, 26) in f
    assert date(2027, 5, 27) in f


@pytest.mark.parametrize("dia", [
    date(2026, 1, 1), date(2026, 4, 21), date(2026, 5, 1), date(2026, 9, 7), date(2026, 10, 12),
    date(2026, 11, 2), date(2026, 11, 15), date(2026, 11, 20), date(2026, 12, 25),
])
def test_feriados_fixos(dia):
    assert eh_feriado(dia)


def test_dia_comum_nao_e_feriado():
    assert not eh_feriado(date(2026, 11, 5))
    assert not eh_feriado(date(2026, 4, 5))  # a Páscoa é domingo e não consta


def test_sao_treze_feriados_por_ano():
    assert len(feriados_nacionais(2026)) == 13
