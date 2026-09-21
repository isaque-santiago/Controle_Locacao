"""Testes de src/domain/agenda_cobrancas.py (Fase 2)."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.agenda_cobrancas import gerar_agenda

_VALOR = Decimal("100.00")


class TestGerarAgenda:
    def test_diario(self):
        agenda = gerar_agenda(date(2026, 1, 1), "diario", _VALOR, date(2026, 1, 3))
        vencimentos = [p["vencimento"] for p in agenda]
        assert vencimentos == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
        assert [p["numero"] for p in agenda] == [1, 2, 3]

    def test_semanal(self):
        agenda = gerar_agenda(date(2026, 1, 1), "semanal", _VALOR, date(2026, 1, 22))
        vencimentos = [p["vencimento"] for p in agenda]
        assert vencimentos == [
            date(2026, 1, 1),
            date(2026, 1, 8),
            date(2026, 1, 15),
            date(2026, 1, 22),
        ]

    def test_quinzenal(self):
        agenda = gerar_agenda(date(2026, 1, 1), "quinzenal", _VALOR, date(2026, 2, 1))
        vencimentos = [p["vencimento"] for p in agenda]
        assert vencimentos == [date(2026, 1, 1), date(2026, 1, 16), date(2026, 1, 31)]

    def test_mensal_preserva_o_dia(self):
        agenda = gerar_agenda(date(2026, 1, 10), "mensal", _VALOR, date(2026, 4, 10))
        vencimentos = [p["vencimento"] for p in agenda]
        assert vencimentos == [
            date(2026, 1, 10),
            date(2026, 2, 10),
            date(2026, 3, 10),
            date(2026, 4, 10),
        ]

    def test_mensal_mes_curto_usa_ultimo_dia(self):
        # 2026 não é bissexto: 31/01 -> 28/02; a partir daí o dia 28 "gruda" nos meses seguintes.
        agenda = gerar_agenda(date(2026, 1, 31), "mensal", _VALOR, date(2026, 4, 30))
        vencimentos = [p["vencimento"] for p in agenda]
        assert vencimentos == [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 28),
            date(2026, 4, 28),
        ]

    def test_mensal_ano_bissexto_29_fevereiro(self):
        agenda = gerar_agenda(date(2024, 1, 31), "mensal", _VALOR, date(2024, 2, 29))
        vencimentos = [p["vencimento"] for p in agenda]
        assert vencimentos == [date(2024, 1, 31), date(2024, 2, 29)]

    def test_data_fim_igual_inicio_gera_uma_parcela(self):
        agenda = gerar_agenda(date(2026, 1, 1), "mensal", _VALOR, date(2026, 1, 1))
        assert len(agenda) == 1
        assert agenda[0] == {"numero": 1, "vencimento": date(2026, 1, 1), "valor": _VALOR}

    def test_valor_de_cada_parcela_igual_ao_periodo(self):
        agenda = gerar_agenda(date(2026, 1, 1), "semanal", _VALOR, date(2026, 1, 15))
        assert all(p["valor"] == _VALOR for p in agenda)

    def test_periodicidade_invalida_levanta_erro(self):
        with pytest.raises(ValueError):
            gerar_agenda(date(2026, 1, 1), "anual", _VALOR, date(2026, 2, 1))

    def test_data_fim_anterior_ao_inicio_levanta_erro(self):
        with pytest.raises(ValueError):
            gerar_agenda(date(2026, 1, 10), "mensal", _VALOR, date(2026, 1, 1))
