"""Testes de src/domain/troca_oleo.py (Fase 7)."""

from decimal import Decimal

import pytest

from src.domain.troca_oleo import avaliar_troca_oleo, validar_km_informado

_MULTA = Decimal("50.00")


class TestValidarKmInformado:
    def test_numero_simples(self):
        assert validar_km_informado("12500") == 12500

    def test_aceita_ponto_de_milhar_e_espacos(self):
        assert validar_km_informado(" 12.500 ") == 12500

    @pytest.mark.parametrize("texto", ["", "  ", "abc", "-10", "12,5", None])
    def test_invalido(self, texto):
        with pytest.raises(ValueError):
            validar_km_informado(texto)


class TestAvaliarTrocaOleo:
    def test_dentro_do_intervalo_nao_cobra(self):
        r = avaliar_troca_oleo(5950, 5900, 5000, 1000, _MULTA)
        assert r == {
            "proxima_km": 6000,
            "excedeu": False,
            "km_excedente": 0,
            "multa": Decimal("0.00"),
        }

    def test_exatamente_na_proxima_km_nao_cobra(self):
        r = avaliar_troca_oleo(6000, 5900, 5000, 1000, _MULTA)
        assert r["excedeu"] is False
        assert r["multa"] == Decimal("0.00")

    def test_um_km_acima_cobra_multa_fixa(self):
        r = avaliar_troca_oleo(6001, 5900, 5000, 1000, _MULTA)
        assert r["excedeu"] is True
        assert r["km_excedente"] == 1
        assert r["multa"] == Decimal("50.00")

    def test_multa_e_fixa_nao_cresce_com_o_excesso(self):
        r = avaliar_troca_oleo(7500, 5900, 5000, 1000, _MULTA)
        assert r["km_excedente"] == 1500
        assert r["multa"] == Decimal("50.00")

    def test_sem_multa_configurada_aponta_excesso_mas_nao_cobra(self):
        r = avaliar_troca_oleo(6500, 5900, 5000, 1000, Decimal("0"))
        assert r["excedeu"] is True
        assert r["multa"] == Decimal("0.00")

    def test_sem_troca_anterior_conta_a_partir_de_zero(self):
        r = avaliar_troca_oleo(1200, 800, None, 1000, _MULTA)
        assert r["proxima_km"] == 1000
        assert r["excedeu"] is True

    def test_plano_sem_intervalo_em_km_nunca_excede(self):
        r = avaliar_troca_oleo(9000, 5900, 5000, None, _MULTA)
        assert r["proxima_km"] is None
        assert r["excedeu"] is False

    def test_km_menor_que_o_atual_e_recusado(self):
        with pytest.raises(ValueError, match="5900"):
            avaliar_troca_oleo(5899, 5900, 5000, 1000, _MULTA)

    def test_km_igual_ao_atual_e_aceito(self):
        assert avaliar_troca_oleo(5900, 5900, 5000, 1000, _MULTA)["excedeu"] is False
