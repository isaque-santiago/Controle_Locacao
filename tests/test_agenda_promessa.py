"""Testes da agenda de promessa de compra e de contratos importados (src/domain/agenda_cobrancas.py)."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.agenda_cobrancas import gerar_agenda

_VALOR = Decimal("550.00")


class TestPromessaDeCompra:
    def test_numeracao_parte_das_parcelas_ja_pagas(self):
        agenda = gerar_agenda(
            date(2026, 10, 12), "semanal", _VALOR, None,
            numero_parcelas=260, parcelas_pagas_inicial=6,
        )
        assert agenda[0]["numero"] == 7
        assert agenda[0]["vencimento"] == date(2026, 10, 12)
        assert agenda[0]["valor"] == _VALOR

    def test_primeira_cobranca_ancora_a_agenda_no_dia_da_semana(self):
        # início do contrato em 27/07 (segunda), controle de cobrança a partir de 12/10 (segunda)
        agenda = gerar_agenda(
            date(2026, 10, 12), "semanal", _VALOR, None,
            parcelas_pagas_inicial=6, primeira_cobranca=date(2026, 10, 12),
        )
        assert [p["vencimento"].weekday() for p in agenda] == [0] * len(agenda)

    def test_para_na_ultima_parcela(self):
        agenda = gerar_agenda(
            date(2026, 10, 5), "semanal", _VALOR, date(2026, 12, 31),
            numero_parcelas=4, parcelas_pagas_inicial=2,
        )
        assert [p["numero"] for p in agenda] == [3, 4]

    def test_promessa_quitada_nao_gera_parcelas(self):
        agenda = gerar_agenda(
            date(2026, 10, 5), "mensal", _VALOR, None,
            numero_parcelas=28, parcelas_pagas_inicial=28,
        )
        assert agenda == []

    def test_mensal_com_primeira_parcela_no_mes_seguinte(self):
        # Leo: 28 parcelas mensais, contrato em 01/10, 1ª parcela em 05/11
        agenda = gerar_agenda(
            date(2026, 10, 1), "mensal", Decimal("500.00"), date(2027, 1, 31),
            numero_parcelas=28, primeira_cobranca=date(2026, 11, 5),
        )
        assert [p["vencimento"] for p in agenda] == [
            date(2026, 11, 5), date(2026, 12, 5), date(2027, 1, 5),
        ]
        assert agenda[0]["numero"] == 1

    def test_sem_promessa_o_comportamento_nao_muda(self):
        agenda = gerar_agenda(date(2026, 10, 5), "semanal", _VALOR, date(2026, 10, 19))
        assert [p["numero"] for p in agenda] == [1, 2, 3]

    @pytest.mark.parametrize("pagas, parcelas", [(5, 4), (-1, 4)])
    def test_parcelas_pagas_invalidas(self, pagas, parcelas):
        with pytest.raises(ValueError):
            gerar_agenda(
                date(2026, 10, 5), "semanal", _VALOR, None,
                numero_parcelas=parcelas, parcelas_pagas_inicial=pagas,
            )

    def test_numero_de_parcelas_deve_ser_positivo(self):
        with pytest.raises(ValueError):
            gerar_agenda(date(2026, 10, 5), "semanal", _VALOR, None, numero_parcelas=0)


class TestValorTotalDaPromessa:
    """Mesma conta da restrição ck_contratos_promessa: total = entrada + parcelas x valor."""

    @pytest.mark.parametrize(
        "parcelas, valor, esperado",
        [
            (260, "550.00", "143000.00"),  # Ronildo
            (200, "650.00", "130000.00"),  # José Henrique
            (200, "550.00", "110000.00"),  # Wagner
            (130, "260.00", "33800.00"),   # Ricardo
            (130, "290.00", "37700.00"),   # Mateus
            (28, "500.00", "14000.00"),    # Leo
        ],
    )
    def test_totais_da_planilha_fecham(self, parcelas, valor, esperado):
        assert Decimal(parcelas) * Decimal(valor) == Decimal(esperado)


class TestEncargosNaPromessa:
    """D3 (22/10/2026): a parcela de promessa é cobrança 'locacao', logo paga encargos; a entrada não."""

    def test_parcela_de_promessa_paga_encargos(self):
        from src.domain.encargos import calcular_encargos

        r = calcular_encargos(
            "locacao", Decimal("550.00"), date(2026, 10, 12), date(2026, 10, 14),
            Decimal("15.00"), Decimal("7.00"),
        )
        assert r["encargos"] == Decimal("29.00")

    def test_entrada_nao_paga_encargos(self):
        from src.domain.encargos import calcular_encargos

        r = calcular_encargos(
            "outros", Decimal("500.00"), date(2026, 10, 12), date(2026, 10, 14),
            Decimal("15.00"), Decimal("7.00"),
        )
        assert r["encargos"] == Decimal("0.00")
