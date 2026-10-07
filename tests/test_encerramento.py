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


def test_resumo_encerramento_junta_caucao_danos_e_cobrancas_canceladas():
    from decimal import Decimal

    from src.domain.encerramento import resumo_encerramento

    parcelas = [
        {"tipo": "caucao", "valor_pago": "400", "situacao": "paga", "vencimento": "2026-08-01"},
        {"tipo": "locacao", "valor_pago": "0", "situacao": "aberta", "vencimento": "2026-10-20"},
        {"tipo": "locacao", "valor_pago": "0", "situacao": "atrasada", "vencimento": "2026-09-01"},
    ]
    resumo = resumo_encerramento(parcelas, "2026-10-10", Decimal("150"))
    assert resumo["caucao_recebida"] == Decimal("400.00")
    assert resumo["devolucao"]["devolucao"] == Decimal("250.00") and resumo["devolucao"]["excedente"] == Decimal("0.00")
    assert [c["vencimento"] for c in resumo["afetadas"]] == ["2026-10-20"]
    excedente = resumo_encerramento(parcelas, "2026-10-10", Decimal("500"))["devolucao"]
    assert excedente["devolucao"] == Decimal("0.00") and excedente["excedente"] == Decimal("100.00")


def test_resumo_encerramento_sem_data_ou_sem_danos_nao_cancela_nem_desconta():
    from decimal import Decimal

    from src.domain.encerramento import resumo_encerramento

    parcelas = [{"tipo": "locacao", "valor_pago": "0", "situacao": "aberta", "vencimento": "2026-10-20"}]
    resumo = resumo_encerramento(parcelas, None, None)
    assert resumo["afetadas"] == [] and resumo["caucao_recebida"] == Decimal("0.00")
    assert resumo["devolucao"]["danos"] == Decimal("0.00")
