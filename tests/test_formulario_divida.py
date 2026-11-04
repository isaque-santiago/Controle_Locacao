"""Formulário de pagamento de parcela de dívida: leitura e validação."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain import formulario_divida as f
from src.domain.formulario_moto import ErroDeCampos

CONTAS = {"c1", "c2"}


def _entrada(**extra):
    return {"data": "2026-11-04", "valor": "1.000,00", "conta_id": "", "observacoes": "", **extra}


def test_valores_iniciais_trazem_hoje_o_saldo_e_nenhuma_conta():
    v = f.pagamento_parcela_inicial(date(2026, 11, 4), Decimal("1000"))
    assert v == {"data": "2026-11-04", "valor": "1.000,00", "conta_id": "", "observacoes": ""}


def test_pagamento_total_quita_a_parcela():
    dados = f.ler_pagamento_parcela(_entrada(conta_id="c1", observacoes=" pix "), Decimal("1000"), CONTAS)
    assert dados == {"data": date(2026, 11, 4), "valor": Decimal("1000.00"), "conta_id": "c1", "observacoes": "pix", "quitada": True}


def test_pagamento_parcial_deixa_o_resto_em_aberto_e_conta_e_opcional():
    dados = f.ler_pagamento_parcela(_entrada(valor="400"), Decimal("1000"), CONTAS)
    assert dados["valor"] == Decimal("400.00") and dados["quitada"] is False
    assert dados["conta_id"] is None and dados["observacoes"] is None


@pytest.mark.parametrize("campo,valor,erro", [
    ("valor", "", "Valor pago"), ("valor", "abc", "Valor pago"), ("valor", "0", "Valor pago"), ("valor", "-5", "Valor pago"),
    ("valor", "1.000,01", "não pode ser maior que o saldo"), ("data", "", "Data do pagamento"),
    ("data", "31/12/2026", "Data do pagamento"), ("conta_id", "outra", "Conta"),
])
def test_entradas_invalidas_dizem_qual_campo_corrigir(campo, valor, erro):
    with pytest.raises(ErroDeCampos) as e:
        f.ler_pagamento_parcela(_entrada(**{campo: valor}), Decimal("1000"), CONTAS)
    chave = campo
    assert chave in e.value.erros and erro in e.value.erros[chave]


def test_varios_erros_vem_juntos():
    with pytest.raises(ErroDeCampos) as e:
        f.ler_pagamento_parcela(_entrada(valor="x", data=""), Decimal("1000"), CONTAS)
    assert set(e.value.erros) == {"valor", "data"}
