"""Testes de src/domain/encargos.py (Fase 2): R$ 15 no vencimento + R$ 7 por dia, só locação."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.encargos import calcular_encargos

_MULTA = Decimal("15.00")
_DIARIO = Decimal("7.00")
_VENCIMENTO = date(2026, 1, 10)


def _calcular(data_referencia, saldo="500.00", tipo="locacao", vencimento=_VENCIMENTO):
    return calcular_encargos(
        tipo=tipo,
        saldo=Decimal(saldo),
        vencimento=vencimento,
        data_referencia=data_referencia,
        multa_valor=_MULTA,
        adicional_diario_valor=_DIARIO,
    )


class TestCalcularEncargos:
    def test_antes_do_vencimento_nao_gera_encargos(self):
        resultado = _calcular(date(2026, 1, 5))
        assert resultado["dias_atraso"] == 0
        assert resultado["multa"] == Decimal("0.00")
        assert resultado["adicional_diario"] == Decimal("0.00")
        assert resultado["encargos"] == Decimal("0.00")
        assert resultado["total"] == Decimal("500.00")

    def test_no_dia_do_vencimento_cobra_so_a_multa_fixa(self):
        resultado = _calcular(_VENCIMENTO)
        assert resultado["dias_atraso"] == 0
        assert resultado["multa"] == Decimal("15.00")
        assert resultado["adicional_diario"] == Decimal("0.00")
        assert resultado["total"] == Decimal("515.00")

    @pytest.mark.parametrize(
        "dias,esperado",
        [(1, "22.00"), (2, "29.00"), (3, "36.00"), (10, "85.00")],
    )
    def test_cada_dia_apos_o_vencimento_soma_o_valor_diario(self, dias, esperado):
        resultado = _calcular(date(2026, 1, 10 + dias))
        assert resultado["dias_atraso"] == dias
        assert resultado["multa"] == Decimal("15.00")
        assert resultado["adicional_diario"] == Decimal("7.00") * dias
        assert resultado["encargos"] == Decimal(esperado)
        assert resultado["total"] == Decimal("500.00") + Decimal(esperado)

    def test_nao_ha_carencia(self):
        # 1 dia de atraso já cobra multa + diário (não existe tolerância).
        resultado = _calcular(date(2026, 1, 11))
        assert resultado["encargos"] == Decimal("22.00")

    def test_encargo_nao_depende_do_saldo(self):
        parcial = _calcular(date(2026, 1, 13), saldo="100.00")
        cheio = _calcular(date(2026, 1, 13), saldo="500.00")
        assert parcial["encargos"] == cheio["encargos"] == Decimal("36.00")
        assert parcial["total"] == Decimal("136.00")

    def test_saldo_zerado_nao_gera_encargos(self):
        resultado = _calcular(date(2026, 1, 20), saldo="0.00")
        assert resultado["encargos"] == Decimal("0.00")
        assert resultado["total"] == Decimal("0.00")

    @pytest.mark.parametrize("tipo", ["caucao", "dano", "multa_transito", "multa_manutencao", "outros"])
    def test_so_cobranca_de_locacao_tem_encargos(self, tipo):
        resultado = _calcular(date(2026, 1, 20), tipo=tipo)
        assert resultado["dias_atraso"] == 10
        assert resultado["encargos"] == Decimal("0.00")
        assert resultado["total"] == Decimal("500.00")

    def test_valores_configurados_sao_usados(self):
        resultado = calcular_encargos(
            "locacao", Decimal("500.00"), _VENCIMENTO, date(2026, 1, 12),
            Decimal("20.00"), Decimal("5.50"),
        )
        assert resultado["encargos"] == Decimal("31.00")

    def test_valores_sao_arredondados_a_duas_casas(self):
        resultado = calcular_encargos(
            "locacao", Decimal("500.00"), _VENCIMENTO, date(2026, 1, 11),
            Decimal("15.005"), Decimal("0.125"),
        )
        # half-up: 15.005 -> 15.01 e 0.125 * 1 dia -> 0.13
        assert resultado["multa"] == Decimal("15.01")
        assert resultado["adicional_diario"] == Decimal("0.13")

    def test_virada_de_mes(self):
        resultado = _calcular(date(2026, 2, 2), vencimento=date(2026, 1, 30))
        assert resultado["dias_atraso"] == 3
        assert resultado["encargos"] == Decimal("36.00")
