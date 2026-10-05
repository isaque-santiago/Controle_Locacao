"""A parte da caução retida para cobrir danos conta como receita da moto (seção 14.3)."""

from datetime import date
from decimal import Decimal

from src.domain.relatorios import consolidar

MOTOS = [{"id": "m", "placa": "ABC1D23", "modelo": "CG"}]


def _consolidar(contratos, inicio=date(2026, 9, 1), fim=date(2026, 9, 30), pagamentos=(), cobrancas=()):
    return consolidar(MOTOS, contratos, list(cobrancas), list(pagamentos), [], [], [], inicio, fim)


def _contrato(retido, encerramento="2026-09-20"):
    return {"id": "c", "moto_id": "m", "caucao_desconto_danos": retido, "data_encerramento": encerramento}


def test_caucao_retida_entra_na_receita_da_moto():
    r = _consolidar([_contrato("300.00")])
    assert r["resultado"][0]["receita_recebida"] == Decimal("300.00")
    assert r["resultado"][0]["resultado"] == Decimal("300.00")


def test_soma_com_os_pagamentos_do_periodo():
    cobrancas = [{"id": "p", "contrato_id": "c", "tipo": "locacao"}]
    pagamentos = [{"cobranca_id": "p", "valor": "350.00", "multa_juros": "0", "data_pagamento": "2026-09-10"}]
    r = _consolidar([_contrato("300.00")], pagamentos=pagamentos, cobrancas=cobrancas)
    assert r["resultado"][0]["receita_recebida"] == Decimal("650.00")


def test_cai_no_mes_do_encerramento_no_fluxo_de_caixa():
    r = _consolidar([_contrato("300.00", "2026-09-20")])
    assert [m["receita_recebida"] for m in r["fluxo"]] == [Decimal("300.00")]
    assert r["fluxo"][0]["mes"] == "2026-09"


def test_fora_do_periodo_nao_conta():
    r = _consolidar([_contrato("300.00", "2026-10-02")])
    assert r["resultado"][0]["receita_recebida"] == Decimal("0")


def test_sem_desconto_ou_contrato_ativo_nao_conta():
    assert _consolidar([_contrato("0.00")])["resultado"][0]["receita_recebida"] == Decimal("0")
    ativo = {"id": "c", "moto_id": "m", "caucao_desconto_danos": "0", "data_encerramento": None}
    assert _consolidar([ativo])["resultado"][0]["receita_recebida"] == Decimal("0")


def test_contratos_antigos_sem_a_coluna_continuam_funcionando():
    assert _consolidar([{"id": "c", "moto_id": "m"}])["resultado"][0]["receita_recebida"] == Decimal("0")
