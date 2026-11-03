"""Regras puras da página de Relatórios do frontend web."""

from datetime import date

from src.domain import relatorios_lista as r

HOJE = date(2026, 10, 8)


def test_aba_e_visao_invalidas_voltam_ao_padrao():
    assert r.aba_valida("fluxo") == "fluxo" and r.aba_valida("x") == "resultado" and r.aba_valida(None) == "resultado"
    assert r.visao_valida("moto") == "moto" and r.visao_valida("x") == "modelo" and r.visao_valida(None) == "modelo"


def test_periodo_padrao_vai_do_primeiro_dia_do_mes_ate_hoje():
    assert r.ler_periodo(None, None, HOJE) == (date(2026, 10, 1), HOJE, None)
    assert r.ler_periodo("", "", HOJE) == (date(2026, 10, 1), HOJE, None)


def test_periodo_informado_e_data_invalida_cai_no_padrao():
    assert r.ler_periodo("2026-01-05", "2026-03-31", HOJE) == (date(2026, 1, 5), date(2026, 3, 31), None)
    assert r.ler_periodo("32/13/2026", "abc", HOJE) == (date(2026, 10, 1), HOJE, None)
    assert r.ler_periodo("2026-09-01", None, HOJE) == (date(2026, 9, 1), HOJE, None)


def test_periodo_invertido_devolve_o_erro():
    inicio, fim, erro = r.ler_periodo("2026-10-08", "2026-10-01", HOJE)
    assert (inicio, fim) == (date(2026, 10, 8), date(2026, 10, 1)) and erro == r.MENSAGEM_PERIODO_INVERTIDO
    assert r.ler_periodo("2026-10-08", "2026-10-08", HOJE)[2] is None
