"""Testes de src/domain/encargos.py (Fase 2)."""

from datetime import date
from decimal import Decimal

from src.domain.encargos import calcular_encargos

_MULTA_PADRAO = Decimal("2.00")
_JUROS_PADRAO = Decimal("1.00")


class TestCalcularEncargos:
    def test_sem_atraso_nao_gera_encargos(self):
        resultado = calcular_encargos(
            saldo=Decimal("1000.00"),
            vencimento=date(2026, 1, 10),
            data_referencia=date(2026, 1, 10),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
        )
        assert resultado["dias_atraso"] == 0
        assert resultado["multa"] == Decimal("0.00")
        assert resultado["juros"] == Decimal("0.00")
        assert resultado["total"] == Decimal("1000.00")

    def test_pagamento_antecipado_nao_gera_encargos(self):
        resultado = calcular_encargos(
            saldo=Decimal("1000.00"),
            vencimento=date(2026, 1, 10),
            data_referencia=date(2026, 1, 5),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
        )
        assert resultado["dias_atraso"] == 0
        assert resultado["total"] == Decimal("1000.00")

    def test_atraso_dez_dias_multa_e_juros_pro_rata(self):
        resultado = calcular_encargos(
            saldo=Decimal("1000.00"),
            vencimento=date(2026, 1, 10),
            data_referencia=date(2026, 1, 20),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
        )
        assert resultado["dias_atraso"] == 10
        assert resultado["multa"] == Decimal("20.00")
        assert resultado["juros"] == Decimal("3.33")
        assert resultado["total"] == Decimal("1023.33")

    def test_carencia_absorve_atraso_pequeno(self):
        resultado = calcular_encargos(
            saldo=Decimal("1000.00"),
            vencimento=date(2026, 1, 10),
            data_referencia=date(2026, 1, 13),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
            carencia_dias=3,
        )
        assert resultado["dias_atraso"] == 0
        assert resultado["total"] == Decimal("1000.00")

    def test_carencia_desconta_dias_do_atraso(self):
        resultado = calcular_encargos(
            saldo=Decimal("1000.00"),
            vencimento=date(2026, 1, 10),
            data_referencia=date(2026, 1, 20),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
            carencia_dias=3,
        )
        assert resultado["dias_atraso"] == 7

    def test_saldo_parcial_calcula_sobre_o_saldo(self):
        resultado = calcular_encargos(
            saldo=Decimal("400.00"),
            vencimento=date(2026, 1, 10),
            data_referencia=date(2026, 1, 20),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
        )
        assert resultado["multa"] == Decimal("8.00")
        assert resultado["total"] == Decimal("400.00") + resultado["multa"] + resultado["juros"]

    def test_arredondamento_meio_para_cima(self):
        # 375 * 1% / 30 * 1 dia = 0.125 -> half-up arredonda para 0.13 (não banker's rounding)
        resultado = calcular_encargos(
            saldo=Decimal("375.00"),
            vencimento=date(2026, 1, 1),
            data_referencia=date(2026, 1, 2),
            multa_percentual=_MULTA_PADRAO,
            juros_mensal_percentual=_JUROS_PADRAO,
        )
        assert resultado["juros"] == Decimal("0.13")
