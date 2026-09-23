"""Testes de src/domain/painel_cobrancas.py."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.painel_cobrancas import mensagem_cobranca, pertence_a_aba, resumo_atraso

HOJE = date(2026, 9, 21)


@pytest.mark.parametrize(
    "situacao, vencimento, aba, esperado",
    [
        ("aberta", HOJE, "Hoje", True),
        ("atrasada", HOJE, "Hoje", True),
        ("paga", HOJE, "Hoje", False),
        ("atrasada", date(2026, 9, 18), "Atrasadas", True),
        ("aberta", HOJE, "Atrasadas", False),
        ("aberta", date(2026, 9, 22), "Próximos 7 dias", True),
        ("aberta", date(2026, 9, 28), "Próximos 7 dias", True),
        ("aberta", date(2026, 9, 29), "Próximos 7 dias", False),
        ("aberta", HOJE, "Próximos 7 dias", False),
        ("paga", date(2026, 9, 1), "Pagas", True),
        ("cancelada", date(2026, 9, 22), "Próximos 7 dias", False),
    ],
)
def test_pertence_a_aba(situacao, vencimento, aba, esperado):
    assert pertence_a_aba(situacao, vencimento, aba, HOJE) is esperado


def test_aba_desconhecida():
    with pytest.raises(ValueError):
        pertence_a_aba("aberta", HOJE, "Outra", HOJE)


def test_resumo_atraso_soma_saldos_e_conta_clientes_distintos():
    linhas = [
        {"situacao": "atrasada", "saldo": "780.00", "cliente_id": "a"},
        {"situacao": "atrasada", "saldo": 220, "cliente_id": "b"},
        {"situacao": "atrasada", "saldo": "0.10", "cliente_id": "a"},
        {"situacao": "aberta", "saldo": 900, "cliente_id": "c"},
    ]
    assert resumo_atraso(linhas) == (Decimal("1000.10"), 2)


def test_mensagem_com_e_sem_atraso():
    atrasada = mensagem_cobranca("Maria", "XYZ4E56", "18/09/2026", "R$ 780,00", 3)
    assert "em atraso há 3 dia(s)" in atrasada and "R$ 780,00" in atrasada
    assert "vence na data indicada" in mensagem_cobranca("Maria", "X", "21/09/2026", "R$ 1,00")
