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


# ---------------------------------------------------------------- outros tipos de dívida --


def _divida(**extra):
    return {"tipo": "moto_fiado", "credor": "Nilson", "valor_original": "9.675,00", "numero_parcelas": "", "valor_parcela": "",
            "dia_vencimento": "", "saldo_confirmado": "", "moto_id": "", "descricao": "", "observacoes": "", **extra}


def test_tipos_da_lista_nao_incluem_a_compra_parcelada():
    tipos = dict(f.tipos_para_selecao())
    assert set(tipos) == {"moto_fiado", "financiamento", "fornecedor", "rastreador", "emprestimo"}
    assert tipos["moto_fiado"] == "Moto fiado" and tipos["emprestimo"] == "Empréstimo"
    assert set(f.divida_inicial()) == set(f.CAMPOS_DIVIDA)


def test_divida_simples_so_com_o_essencial():
    d = f.ler_divida(_divida(), MOTOS)
    assert d == {"tipo": "moto_fiado", "credor": "Nilson", "valor_original": Decimal("9675.00"), "numero_parcelas": None,
                 "valor_parcela": None, "dia_vencimento": None, "saldo_confirmado": None, "moto_id": None,
                 "descricao": None, "observacoes": None}


def test_divida_completa_do_tia1b71():
    d = f.ler_divida(_divida(tipo="financiamento", credor="Nicolas", valor_original="21.901,92", numero_parcelas="24",
                             valor_parcela="912,58", dia_vencimento="28", saldo_confirmado="20.989,34", moto_id="m1",
                             descricao=" Financiamento ", observacoes="Informado pelo Alisson"), MOTOS)
    assert d["numero_parcelas"] == 24 and d["valor_parcela"] == Decimal("912.58") and d["dia_vencimento"] == 28
    assert d["saldo_confirmado"] == Decimal("20989.34") and d["moto_id"] == "m1" and d["descricao"] == "Financiamento"


def test_valor_original_vazio_vale_zero_e_saldo_confirmado_zero_e_aceito():
    d = f.ler_divida(_divida(valor_original="", saldo_confirmado="0"), MOTOS)
    assert d["valor_original"] == Decimal("0.00") and d["saldo_confirmado"] == Decimal("0.00")


@pytest.mark.parametrize("campo,valor,erro", [
    ("tipo", "compra_parcelada", "Tipo"), ("tipo", "", "Tipo"), ("credor", "", "Credor"), ("credor", "x" * 121, "no máximo 120"),
    ("valor_original", "-1", "Valor original"), ("valor_original", "abc", "Valor original"),
    ("numero_parcelas", "0", "Número de parcelas"), ("dia_vencimento", "32", "Dia do vencimento"),
    ("dia_vencimento", "0", "Dia do vencimento"), ("saldo_confirmado", "-5", "Saldo confirmado"), ("moto_id", "x", "Moto"),
])
def test_divida_com_campo_invalido_nao_passa(campo, valor, erro):
    extra = {campo: valor}
    if campo == "numero_parcelas":
        extra["valor_parcela"] = "100"
    with pytest.raises(ErroDeCampos) as e:
        f.ler_divida(_divida(**extra), MOTOS)
    assert campo in e.value.erros and erro in e.value.erros[campo]


def test_parcelas_e_valor_da_parcela_vem_juntos():
    with pytest.raises(ErroDeCampos) as e:
        f.ler_divida(_divida(numero_parcelas="10"), MOTOS)
    assert set(e.value.erros) == {"valor_parcela"}
    with pytest.raises(ErroDeCampos) as e:
        f.ler_divida(_divida(valor_parcela="100"), MOTOS)
    assert set(e.value.erros) == {"numero_parcelas"}


def test_pagamento_direto_usa_a_mensagem_do_saldo_da_divida():
    with pytest.raises(ErroDeCampos) as e:
        f.ler_pagamento_parcela(_entrada(valor="5.000,00"), Decimal("3425"), CONTAS, alvo="da dívida")
    assert "não pode ser maior que o saldo da dívida (R$ 3.425,00)" in e.value.erros["valor"]
    assert f.ler_pagamento_parcela(_entrada(valor="3.425,00"), Decimal("3425"), CONTAS, alvo="da dívida")["quitada"] is True


# ---------------------------------------------------------------- editar e confirmar saldo --

DIVIDA_BANCO = {"credor": "Nilson", "valor_original": "9675.00", "numero_parcelas": None, "valor_parcela": None,
                "dia_vencimento": None, "moto_id": None, "descricao": None, "observacoes": "Informado em 16/10"}


def test_campos_editaveis_da_compra_parcelada_sao_so_os_de_identificacao():
    assert f.campos_editaveis("compra_parcelada") == ("credor", "moto_id", "descricao", "observacoes")
    assert "valor_original" in f.campos_editaveis("moto_fiado")


def test_edicao_inicial_traz_o_que_a_divida_tem():
    v = f.edicao_inicial({**DIVIDA_BANCO, "numero_parcelas": 24, "valor_parcela": "912.58", "dia_vencimento": 28, "moto_id": "m1"})
    assert v["credor"] == "Nilson" and v["valor_original"] == "9.675,00" and v["numero_parcelas"] == "24"
    assert v["valor_parcela"] == "912,58" and v["dia_vencimento"] == "28" and v["moto_id"] == "m1"
    assert f.edicao_inicial(DIVIDA_BANCO)["numero_parcelas"] == "" and f.edicao_inicial(DIVIDA_BANCO)["valor_parcela"] == ""


def _edicao(**extra):
    return {**f.edicao_inicial(DIVIDA_BANCO), **extra}


def test_edicao_de_moto_fiado_muda_valores_e_limpa_o_que_ficou_vazio():
    d = f.ler_edicao_divida(_edicao(valor_original="9.000,00", observacoes="", moto_id="m1", dia_vencimento="10"), "moto_fiado", MOTOS)
    assert d["valor_original"] == Decimal("9000.00") and d["observacoes"] is None and d["moto_id"] == "m1"
    assert d["dia_vencimento"] == 10 and d["numero_parcelas"] is None and d["valor_parcela"] is None


def test_edicao_da_compra_parcelada_ignora_valores_e_parcelas():
    d = f.ler_edicao_divida(_edicao(credor="Álvaro", valor_original="1", numero_parcelas="2", valor_parcela="3"), "compra_parcelada", MOTOS)
    assert set(d) == {"credor", "moto_id", "descricao", "observacoes"} and d["credor"] == "Álvaro"


@pytest.mark.parametrize("campo,valor,erro", [
    ("credor", "", "Credor"), ("credor", "x" * 121, "no máximo 120"), ("valor_original", "-1", "Valor original"),
    ("numero_parcelas", "0", "Número de parcelas"), ("dia_vencimento", "32", "Dia do vencimento"), ("moto_id", "x", "Moto"),
])
def test_edicao_invalida_nao_passa(campo, valor, erro):
    extra = {campo: valor}
    if campo == "numero_parcelas":
        extra["valor_parcela"] = "100"
    with pytest.raises(ErroDeCampos) as e:
        f.ler_edicao_divida(_edicao(**extra), "emprestimo", MOTOS)
    assert campo in e.value.erros and erro in e.value.erros[campo]


def test_edicao_exige_parcelas_e_valor_juntos():
    with pytest.raises(ErroDeCampos) as e:
        f.ler_edicao_divida(_edicao(numero_parcelas="10"), "emprestimo", MOTOS)
    assert set(e.value.erros) == {"valor_parcela"}


def test_saldo_inicial_prefere_o_confirmado_e_usa_hoje():
    hoje = date(2026, 11, 5)
    assert f.saldo_inicial({"saldo_confirmado": "3425.00"}, Decimal("5600"), hoje) == {"saldo": "3.425,00", "data": "2026-11-05"}
    assert f.saldo_inicial({"saldo_confirmado": None}, Decimal("5600"), hoje)["saldo"] == "5.600,00"
    assert f.saldo_inicial({"saldo_confirmado": "0"}, Decimal("5600"), hoje)["saldo"] == "0,00"


def test_confirmar_saldo_le_valor_e_data():
    d = f.ler_saldo_confirmado({"saldo": "3.425,00", "data": "2026-10-16", "acao": "confirmar"}, date(2026, 11, 5))
    assert d == {"saldo_confirmado": Decimal("3425.00"), "confirmado_em": date(2026, 10, 16)}
    assert f.ler_saldo_confirmado({"saldo": "0", "data": "2026-11-05"}, date(2026, 11, 5))["saldo_confirmado"] == Decimal("0.00")


def test_limpar_a_confirmacao_nao_valida_campos():
    assert f.ler_saldo_confirmado({"acao": "limpar", "saldo": "lixo", "data": ""}, date(2026, 11, 5)) == {
        "saldo_confirmado": None, "confirmado_em": None}


@pytest.mark.parametrize("entrada,campo,erro", [
    ({"saldo": "", "data": "2026-11-05"}, "saldo", "Saldo confirmado"), ({"saldo": "-1", "data": "2026-11-05"}, "saldo", "Saldo confirmado"),
    ({"saldo": "10", "data": ""}, "data", "Data da confirmação"), ({"saldo": "10", "data": "05/11/2026"}, "data", "Data da confirmação"),
    ({"saldo": "10", "data": "2026-11-06"}, "data", "no futuro"),
])
def test_confirmar_saldo_recusa_entradas_invalidas(entrada, campo, erro):
    with pytest.raises(ErroDeCampos) as e:
        f.ler_saldo_confirmado(entrada, date(2026, 11, 5))
    assert campo in e.value.erros and erro in e.value.erros[campo]


# ---------------------------------------------------------------- trocar o tipo --


def test_campos_editaveis_incluem_o_tipo_so_fora_da_compra_parcelada():
    assert "tipo" in f.campos_editaveis("moto_fiado") and "tipo" not in f.campos_editaveis("compra_parcelada")


def test_edicao_inicial_traz_o_tipo_atual():
    assert f.edicao_inicial({**DIVIDA_BANCO, "tipo": "moto_fiado"})["tipo"] == "moto_fiado"


def test_trocar_o_tipo_entre_os_cinco():
    d = f.ler_edicao_divida(_edicao(tipo="financiamento"), "moto_fiado", MOTOS)
    assert d["tipo"] == "financiamento"


def test_sem_tipo_na_entrada_mantem_o_atual():
    d = f.ler_edicao_divida(_edicao(tipo=""), "emprestimo", MOTOS)
    assert d["tipo"] == "emprestimo"


@pytest.mark.parametrize("tipo", ["compra_parcelada", "qualquer"])
def test_nao_troca_para_compra_parcelada_nem_para_tipo_desconhecido(tipo):
    with pytest.raises(ErroDeCampos) as e:
        f.ler_edicao_divida(_edicao(tipo=tipo), "moto_fiado", MOTOS)
    assert "tipo" in e.value.erros and "Tipo" in e.value.erros["tipo"]


def test_a_compra_parcelada_ignora_o_tipo_enviado():
    d = f.ler_edicao_divida(_edicao(tipo="moto_fiado"), "compra_parcelada", MOTOS)
    assert "tipo" not in d


# ---------------------------------------------------------------- editar parcela --

PARCELA = {"vencimento": "2026-11-28", "valor": "1000.00"}


def test_edicao_da_parcela_parte_do_que_ela_tem():
    assert f.edicao_parcela_inicial(PARCELA) == {"vencimento": "2026-11-28", "valor": "1.000,00"}
    assert f.edicao_parcela_inicial({"vencimento": None, "valor": "500"}) == {"vencimento": "", "valor": "500,00"}


def test_parcela_sem_pagamento_muda_vencimento_e_valor():
    d = f.ler_edicao_parcela({"vencimento": "2026-12-15", "valor": "1.200,00"}, Decimal("0"))
    assert d == {"vencimento": date(2026, 12, 15), "valor": Decimal("1200.00")}


def test_parcela_com_pagamento_so_muda_o_vencimento_e_ignora_o_valor():
    d = f.ler_edicao_parcela({"vencimento": "2026-12-15", "valor": "abc"}, Decimal("400"))
    assert d == {"vencimento": date(2026, 12, 15)}


def test_vencimento_vazio_deixa_a_parcela_sem_data():
    assert f.ler_edicao_parcela({"vencimento": "", "valor": "1000"}, Decimal("0"))["vencimento"] is None


@pytest.mark.parametrize("entrada,campo,erro", [
    ({"vencimento": "28/12/2026", "valor": "10"}, "vencimento", "Vencimento"),
    ({"vencimento": "2026-12-01", "valor": ""}, "valor", "Valor da parcela"),
    ({"vencimento": "2026-12-01", "valor": "0"}, "valor", "Valor da parcela"),
    ({"vencimento": "2026-12-01", "valor": "-5"}, "valor", "Valor da parcela"),
])
def test_edicao_de_parcela_invalida(entrada, campo, erro):
    with pytest.raises(ErroDeCampos) as e:
        f.ler_edicao_parcela(entrada, Decimal("0"))
    assert campo in e.value.erros and erro in e.value.erros[campo]


# ---------------------------------------------------------------- editar pagamento --

PAGAMENTO = {"data": "2026-10-28", "valor": "1000.00", "conta_id": "c1", "observacoes": None, "data_estimada": True}


def test_edicao_do_pagamento_parte_do_que_ele_tem():
    assert f.edicao_pagamento_inicial(PAGAMENTO) == {"data": "2026-10-28", "valor": "1.000,00", "conta_id": "c1", "observacoes": "", "data_estimada": "1"}
    assert f.edicao_pagamento_inicial({**PAGAMENTO, "conta_id": None, "data_estimada": False})["data_estimada"] == ""


def _pag(**extra):
    return {"data": "2026-10-29", "valor": "900,00", "conta_id": "", "observacoes": " corrigido ", "data_estimada": "", **extra}


def test_pagamento_corrigido():
    d = f.ler_edicao_pagamento(_pag(conta_id="c2", data_estimada="1"), Decimal("1000"), CONTAS)
    assert d == {"data": date(2026, 10, 29), "valor": Decimal("900.00"), "conta_id": "c2", "observacoes": "corrigido", "data_estimada": True}
    assert f.ler_edicao_pagamento(_pag(), Decimal("1000"), CONTAS)["data_estimada"] is False


@pytest.mark.parametrize("campo,valor,erro", [
    ("data", "", "Data do pagamento"), ("data", "29/10/2026", "Data do pagamento"), ("valor", "", "Valor pago"),
    ("valor", "0", "Valor pago"), ("valor", "1.000,01", "não pode passar de R$ 1.000,00"), ("conta_id", "x", "Conta"),
])
def test_edicao_de_pagamento_invalida(campo, valor, erro):
    with pytest.raises(ErroDeCampos) as e:
        f.ler_edicao_pagamento(_pag(**{campo: valor}), Decimal("1000"), CONTAS)
    assert campo in e.value.erros and erro in e.value.erros[campo]
