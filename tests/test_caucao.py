"""Testes de src/domain/caucao.py: danos descontados da caução no encerramento."""

from decimal import Decimal

import pytest

from src.domain.caucao import calcular_devolucao_caucao, caucao_paga


class TestCalcularDevolucaoCaucao:
    def test_sem_danos_devolve_a_caucao_inteira(self):
        r = calcular_devolucao_caucao(Decimal("1000.00"), Decimal("0"))
        assert r["desconto"] == Decimal("0.00")
        assert r["devolucao"] == Decimal("1000.00")
        assert r["excedente"] == Decimal("0.00")

    def test_dano_menor_que_a_caucao_e_descontado(self):
        # exemplo do responsável: caução R$ 1.000, dano R$ 300 -> devolve R$ 700
        r = calcular_devolucao_caucao(Decimal("1000.00"), Decimal("300.00"))
        assert r["desconto"] == Decimal("300.00")
        assert r["devolucao"] == Decimal("700.00")
        assert r["excedente"] == Decimal("0.00")

    def test_dano_igual_a_caucao_zera_a_devolucao(self):
        r = calcular_devolucao_caucao(Decimal("500.00"), Decimal("500.00"))
        assert r["devolucao"] == Decimal("0.00")
        assert r["excedente"] == Decimal("0.00")

    def test_dano_maior_que_a_caucao_cobra_o_excedente(self):
        r = calcular_devolucao_caucao(Decimal("1000.00"), Decimal("1300.00"))
        assert r["desconto"] == Decimal("1000.00")
        assert r["devolucao"] == Decimal("0.00")
        assert r["excedente"] == Decimal("300.00")

    def test_sem_caucao_recebida_todo_o_dano_e_excedente(self):
        r = calcular_devolucao_caucao(Decimal("0"), Decimal("200.00"))
        assert r["devolucao"] == Decimal("0.00")
        assert r["excedente"] == Decimal("200.00")

    def test_aceita_texto_e_arredonda_a_duas_casas(self):
        r = calcular_devolucao_caucao("1000", "0.005")
        assert r["danos"] == Decimal("0.01")
        assert r["devolucao"] == Decimal("999.99")

    def test_soma_desconto_devolucao_e_excedente_fecha_com_os_valores(self):
        r = calcular_devolucao_caucao(Decimal("750.00"), Decimal("1000.00"))
        assert r["desconto"] + r["devolucao"] == r["caucao_paga"]
        assert r["desconto"] + r["excedente"] == r["danos"]

    @pytest.mark.parametrize("caucao,danos", [("-1", "0"), ("100", "-1")])
    def test_valores_negativos_sao_recusados(self, caucao, danos):
        with pytest.raises(ValueError):
            calcular_devolucao_caucao(caucao, danos)


class TestCaucaoPaga:
    def test_soma_so_o_que_foi_pago_nas_cobrancas_de_caucao(self):
        cobrancas = [
            {"tipo": "caucao", "valor": "1000.00", "valor_pago": "1000.00"},
            {"tipo": "locacao", "valor": "300.00", "valor_pago": "300.00"},
            {"tipo": "dano", "valor": "50.00", "valor_pago": "50.00"},
        ]
        assert caucao_paga(cobrancas) == Decimal("1000.00")

    def test_caucao_parcialmente_paga_conta_so_o_pago(self):
        cobrancas = [{"tipo": "caucao", "valor": "1000.00", "valor_pago": "400.00"}]
        assert caucao_paga(cobrancas) == Decimal("400.00")

    def test_sem_caucao_ou_sem_pagamento_e_zero(self):
        assert caucao_paga([]) == Decimal("0.00")
        assert caucao_paga([{"tipo": "caucao", "valor": "500", "valor_pago": None}]) == Decimal("0.00")
