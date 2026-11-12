"""Testes de src/domain/cancelamento_cobranca.py: quando a cobrança pode ser cancelada e a leitura do motivo."""

from decimal import Decimal

import pytest

from src.domain.cancelamento_cobranca import MOTIVO_MAXIMO, ler_cancelamento, motivo_da_recusa, pode_cancelar
from src.domain.formulario_moto import ErroDeCampos


@pytest.mark.parametrize("situacao", ["aberta", "atrasada"])
def test_cobranca_em_aberto_sem_pagamento_pode_ser_cancelada(situacao):
    assert pode_cancelar({"situacao": situacao, "valor_pago": Decimal("0")})
    assert pode_cancelar({"situacao": situacao, "valor_pago": 0})
    assert pode_cancelar({"situacao": situacao, "valor_pago": None})
    assert pode_cancelar({"situacao": situacao})  # sem o campo: nada foi pago


@pytest.mark.parametrize("situacao", ["aberta", "atrasada"])
def test_pagamento_parcial_impede_o_cancelamento(situacao):
    assert not pode_cancelar({"situacao": situacao, "valor_pago": Decimal("0.01")})
    assert not pode_cancelar({"situacao": situacao, "valor_pago": "150.00"})


@pytest.mark.parametrize("situacao", ["paga", "cancelada", None, "outra"])
def test_paga_ja_cancelada_ou_desconhecida_nao_pode(situacao):
    assert not pode_cancelar({"situacao": situacao, "valor_pago": 0})


def test_motivo_da_recusa_explica_cada_caso():
    assert motivo_da_recusa({"situacao": "cancelada"}) == "Esta cobrança já está cancelada."
    assert motivo_da_recusa({"situacao": "paga", "valor_pago": 100}) == "Cobrança paga não pode ser cancelada."
    assert "já tem pagamento registrado" in motivo_da_recusa({"situacao": "atrasada", "valor_pago": Decimal("50")})
    assert motivo_da_recusa({"situacao": "aberta", "valor_pago": 0}) == ""


def test_motivo_valido_perde_os_espacos_das_pontas():
    assert ler_cancelamento({"motivo": "  Lançada por engano  "}) == "Lançada por engano"
    assert ler_cancelamento({"motivo": "abc"}) == "abc"
    assert ler_cancelamento({"motivo": "x" * MOTIVO_MAXIMO}) == "x" * MOTIVO_MAXIMO


@pytest.mark.parametrize("entrada", [{}, {"motivo": ""}, {"motivo": "   "}, {"motivo": "ab"}])
def test_motivo_ausente_ou_curto_e_recusado(entrada):
    with pytest.raises(ErroDeCampos) as erro:
        ler_cancelamento(entrada)
    assert "mínimo 3 letras" in erro.value.erros["motivo"]


def test_motivo_longo_demais_e_recusado():
    with pytest.raises(ErroDeCampos) as erro:
        ler_cancelamento({"motivo": "x" * (MOTIVO_MAXIMO + 1)})
    assert "no máximo 200" in erro.value.erros["motivo"]
