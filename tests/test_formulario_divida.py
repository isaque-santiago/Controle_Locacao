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


# ---------------------------------------------------------------- compra parcelada --

MOTOS = {"m1"}


def _compra(**extra):
    return {"credor": "Celta", "valor_entrada": "5.000,00", "numero_parcelas": "9", "valor_parcela": "1.000,00",
            "primeira_parcela": "2026-05-28", "parcelas_pagas": "6", "data_entrada": "", "conta_id": "", "moto_id": "",
            "descricao": "", "observacoes": "", **extra}


def test_compra_inicial_traz_defaults():
    v = f.compra_inicial(date(2026, 11, 4))
    assert v["primeira_parcela"] == "2026-11-04" and v["valor_entrada"] == "0,00" and v["parcelas_pagas"] == "0"
    assert set(v) == set(f.CAMPOS_COMPRA)


def test_compra_do_celta_calcula_o_total_e_converte_os_tipos():
    d = f.ler_compra_parcelada(_compra(conta_id="c1", moto_id="m1", descricao=" Celta 2008 ", data_entrada="2026-05-01"), CONTAS, MOTOS)
    assert d["valor_total"] == Decimal("14000.00") and d["valor_entrada"] == Decimal("5000.00")
    assert d["numero_parcelas"] == 9 and d["parcelas_pagas"] == 6 and d["primeira_parcela"] == date(2026, 5, 28)
    assert d["data_entrada"] == date(2026, 5, 1) and d["conta_id"] == "c1" and d["moto_id"] == "m1"
    assert d["descricao"] == "Celta 2008" and d["observacoes"] is None


def test_compra_sem_entrada_nem_parcelas_pagas():
    d = f.ler_compra_parcelada(_compra(valor_entrada="", parcelas_pagas=""), CONTAS, MOTOS)
    assert d["valor_entrada"] == Decimal("0.00") and d["valor_total"] == Decimal("9000.00") and d["parcelas_pagas"] == 0
    assert d["data_entrada"] is None and d["conta_id"] is None and d["moto_id"] is None


@pytest.mark.parametrize("campo,valor,erro", [
    ("credor", "", "Credor"), ("credor", "x" * 121, "no máximo 120"), ("valor_entrada", "-1", "Entrada"),
    ("numero_parcelas", "", "Número de parcelas"), ("numero_parcelas", "0", "Número de parcelas"),
    ("numero_parcelas", "121", "Número de parcelas"), ("numero_parcelas", "2,5", "Número de parcelas"),
    ("valor_parcela", "", "Valor da parcela"), ("valor_parcela", "0", "Valor da parcela"),
    ("primeira_parcela", "", "Primeira parcela"), ("primeira_parcela", "28/05/2026", "Primeira parcela"),
    ("parcelas_pagas", "10", "no máximo 9"), ("parcelas_pagas", "-1", "Parcelas já pagas"),
    ("data_entrada", "ontem", "Data da entrada"), ("conta_id", "x", "Conta"), ("moto_id", "x", "Moto"),
])
def test_compra_com_campo_invalido_nao_passa(campo, valor, erro):
    with pytest.raises(ErroDeCampos) as e:
        f.ler_compra_parcelada(_compra(**{campo: valor}), CONTAS, MOTOS)
    assert campo in e.value.erros and erro in e.value.erros[campo]


def test_previa_da_compra_marca_as_pagas_e_calcula_o_saldo():
    d = f.ler_compra_parcelada(_compra(), CONTAS, MOTOS)
    p = f.previa_da_compra(d)
    assert p["valor_total"] == Decimal("14000.00") and p["saldo"] == Decimal("3000.00")
    assert [x["numero"] for x in p["parcelas"]] == list(range(1, 10))
    assert p["parcelas"][0]["vencimento"] == date(2026, 5, 28) and p["parcelas"][8]["vencimento"] == date(2027, 1, 28)
    assert sum(1 for x in p["parcelas"] if x["paga"]) == 6 and p["parcelas"][5]["paga"] and not p["parcelas"][6]["paga"]
