"""Validação do pagamento de cobrança (src/domain/formulario_pagamento.py)."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain import formulario_pagamento as f
from src.domain.formulario_moto import ErroDeCampos

BASE = {"data_pagamento": "2026-10-07", "principal": "204,00", "extras": "0,00", "forma": "pix", "observacoes": ""}


def _erros(entrada, saldo="204"):
    with pytest.raises(ErroDeCampos) as erro:
        f.ler_pagamento(entrada, saldo)
    return erro.value.erros


def test_pagamento_total_quita_e_normaliza_os_dados():
    dados = f.ler_pagamento({**BASE, "extras": "288,00", "observacoes": " pago no balcão "}, "204")
    assert dados == {"data": date(2026, 10, 7), "principal": Decimal("204.00"), "extras": Decimal("288.00"),
                     "forma": "pix", "observacoes": "pago no balcão", "quitada": True}


def test_principal_menor_que_o_saldo_deixa_a_cobranca_em_aberto():
    dados = f.ler_pagamento({**BASE, "principal": "100,00"}, "204")
    assert dados["quitada"] is False and dados["principal"] == Decimal("100.00") and dados["observacoes"] is None


def test_principal_maior_que_o_saldo_e_recusado_com_o_valor_do_saldo():
    mensagem = _erros({**BASE, "principal": "204,01"})["principal"]
    assert "não pode ser maior que o saldo" in mensagem and "R$ 204,00" in mensagem


def test_principal_zero_negativo_ou_texto_e_recusado():
    for valor in ("0,00", "-5", "abc", ""):
        assert "principal" in _erros({**BASE, "principal": valor})


def test_extras_podem_ser_zero_mas_nao_negativos():
    assert f.ler_pagamento({**BASE, "extras": "0"}, "204")["extras"] == Decimal("0.00")
    assert "extras" in _erros({**BASE, "extras": "-1,00"})


def test_um_erro_por_campo_e_forma_precisa_ser_conhecida():
    erros = _erros({"data_pagamento": "", "principal": "x", "extras": "y", "forma": "cheque"})
    assert set(erros) == {"data_pagamento", "principal", "extras", "forma"}


def test_pagamento_inicial_usa_saldo_e_encargos_da_data():
    ini = f.pagamento_inicial(date(2026, 10, 7), Decimal("45"), Decimal("288"))
    assert ini == {"data_pagamento": "2026-10-07", "principal": "45,00", "extras": "288,00", "forma": "pix", "observacoes": ""}
    assert f.texto_do_pagamento({"principal": " 1,5 "})["principal"] == "1,5"


def test_aba_da_cobranca_para_voltar_a_lista_certa():
    hoje = date(2026, 10, 7)
    assert f.aba_da_cobranca("atrasada", "2026-10-01", hoje) == "atrasadas"
    assert f.aba_da_cobranca("aberta", "2026-10-07", hoje) == "hoje"
    assert f.aba_da_cobranca("aberta", "2026-10-10", hoje) == "proximos"
