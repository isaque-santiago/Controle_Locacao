"""Cobranças afetadas pelo encerramento de um contrato (espelha a RPC)."""

from datetime import date
from decimal import Decimal

from src.domain.encerramento import cobrancas_a_cancelar


def _cobranca(id, vencimento, situacao="aberta", valor_pago=0):
    return {"id": id, "vencimento": vencimento, "situacao": situacao, "valor_pago": Decimal(str(valor_pago))}


def test_cancela_so_o_que_vence_depois_e_nao_tem_pagamento():
    cobrancas = [
        _cobranca("antes", "2026-09-10"),
        _cobranca("no_dia", "2026-09-15"),
        _cobranca("depois_b", "2026-11-15"),
        _cobranca("depois_a", "2026-10-15"),
        _cobranca("parcial", "2026-10-20", valor_pago="40.00"),
        _cobranca("paga", "2026-10-25", situacao="paga", valor_pago="100"),
        _cobranca("cancelada", "2026-10-30", situacao="cancelada"),
    ]
    afetadas = cobrancas_a_cancelar(cobrancas, date(2026, 9, 15))
    assert [c["id"] for c in afetadas] == ["depois_a", "depois_b"]


def test_aceita_data_como_texto_iso_e_cobranca_atrasada_sem_pagamento():
    cobrancas = [_cobranca("a", "2026-10-01T00:00:00", situacao="atrasada")]
    assert [c["id"] for c in cobrancas_a_cancelar(cobrancas, "2026-09-30")] == ["a"]


def test_sem_cobrancas_nada_a_cancelar():
    assert cobrancas_a_cancelar([], date(2026, 9, 15)) == []
