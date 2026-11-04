"""Compra a prazo como dívida (Celta: entrada de R$ 5.000 + 9 parcelas mensais de R$ 1.000, dia 28)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.domain.dividas import (
    calendario_parcelas,
    dias_atraso_parcela,
    saldo_compra,
    situacao_parcela,
    validar_compra_parcelada,
)
from src.services import dividas

CELTA = dict(valor_total=Decimal("14000.00"), valor_entrada=Decimal("5000.00"), numero_parcelas=9, valor_parcela=Decimal("1000.00"))


class TestValidacao:
    def test_celta_fecha(self):
        validar_compra_parcelada(**CELTA, parcelas_pagas=6)

    def test_total_que_nao_fecha_e_recusado(self):
        with pytest.raises(ValueError, match="deve ser igual"):
            validar_compra_parcelada(Decimal("8000.00"), Decimal("0"), 9, Decimal("1000.00"))

    @pytest.mark.parametrize("pagas", [-1, 10])
    def test_parcelas_pagas_fora_do_intervalo(self, pagas):
        with pytest.raises(ValueError, match="parcelas pagas"):
            validar_compra_parcelada(**CELTA, parcelas_pagas=pagas)

    def test_parcela_nao_positiva(self):
        with pytest.raises(ValueError, match="valor da parcela"):
            validar_compra_parcelada(Decimal("0"), Decimal("0"), 1, Decimal("0"))


class TestCalendario:
    def test_celta_vai_de_28_05_a_28_01(self):
        datas = calendario_parcelas(date(2026, 5, 28), 9)
        assert datas[0] == date(2026, 5, 28) and datas[-1] == date(2027, 1, 28)
        assert datas[6:] == [date(2026, 11, 28), date(2026, 12, 28), date(2027, 1, 28)]

    def test_mes_curto_usa_o_ultimo_dia_sem_perder_o_dia_original(self):
        datas = calendario_parcelas(date(2026, 1, 31), 4)
        assert datas == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]

    def test_numero_de_parcelas_invalido(self):
        with pytest.raises(ValueError):
            calendario_parcelas(date(2026, 5, 28), 0)


class TestSaldoESituacao:
    def test_saldo_do_celta_depois_de_entrada_e_6_parcelas(self):
        assert saldo_compra(Decimal("14000"), Decimal("5000"), Decimal("1000"), 6) == Decimal("3000.00")

    def test_situacao_da_parcela(self):
        hoje = date(2026, 11, 3)
        assert situacao_parcela(date(2026, 10, 28), Decimal("1000"), Decimal("1000"), hoje) == "paga"
        assert situacao_parcela(date(2026, 10, 28), Decimal("1000"), Decimal("400"), hoje) == "atrasada"
        assert situacao_parcela(date(2026, 11, 28), Decimal("1000"), Decimal("0"), hoje) == "a_vencer"
        assert situacao_parcela(None, Decimal("1000"), Decimal("0"), hoje) == "sem_data"

    def test_dias_de_atraso(self):
        hoje = date(2026, 11, 3)
        assert dias_atraso_parcela(date(2026, 10, 28), Decimal("1000"), Decimal("0"), hoje) == 6
        assert dias_atraso_parcela(date(2026, 10, 28), Decimal("1000"), Decimal("1000"), hoje) == 0
        assert dias_atraso_parcela(date(2026, 11, 28), Decimal("1000"), Decimal("0"), hoje) == 0
        assert dias_atraso_parcela(None, Decimal("1000"), Decimal("0"), hoje) == 0


class TestServico:
    def test_cria_a_compra_enviando_o_payload(self):
        with patch("src.services.dividas.dividas.criar_compra_parcelada", return_value={}) as rpc:
            dividas.criar_compra_parcelada(
                "  Celta  ", primeira_parcela=date(2026, 5, 28), data_entrada=date(2026, 5, 1),
                parcelas_pagas=6, moto_id="m", **CELTA,
            )
        p = rpc.call_args.args[0]
        assert p["credor"] == "Celta" and p["valor_total"] == "14000.00" and p["valor_entrada"] == "5000.00"
        assert p["numero_parcelas"] == 9 and p["primeira_parcela"] == "2026-05-28" and p["parcelas_pagas"] == 6
        assert p["data_entrada"] == "2026-05-01" and p["moto_id"] == "m" and p["conta_id"] is None

    def test_recusa_total_que_nao_fecha_sem_chamar_o_banco(self):
        with patch("src.services.dividas.dividas.criar_compra_parcelada") as rpc:
            with pytest.raises(ValueError, match="deve ser igual"):
                dividas.criar_compra_parcelada("Celta", Decimal("9999"), 9, Decimal("1000"), date(2026, 5, 28), Decimal("5000"))
        rpc.assert_not_called()

    def test_recusa_credor_vazio(self):
        with pytest.raises(ValueError, match="credor"):
            dividas.criar_compra_parcelada("  ", primeira_parcela=date(2026, 5, 28), **CELTA)

    def test_previa_do_calendario(self):
        previa = dividas.previa_calendario(date(2026, 11, 28), 3, Decimal("1000.00"))
        assert [(p["numero"], p["vencimento"]) for p in previa] == [
            (1, date(2026, 11, 28)), (2, date(2026, 12, 28)), (3, date(2027, 1, 28)),
        ]

    def test_paga_parcela_com_saldo_total_por_padrao(self):
        with patch("src.services.dividas.dividas.pagar_parcela", return_value={}) as rpc:
            dividas.pagar_parcela("v", date(2026, 11, 28), observacoes="  Pix  ")
        assert rpc.call_args.args == ("v", date(2026, 11, 28), None, None, "Pix")

    def test_recusa_valor_nao_positivo(self):
        with patch("src.services.dividas.dividas.pagar_parcela") as rpc:
            with pytest.raises(ValueError, match="positivo"):
                dividas.pagar_parcela("v", date(2026, 11, 28), Decimal("0"))
        rpc.assert_not_called()


# ---------------------------------------------------------------- outros tipos e pagamento direto --


def _repo_gravador(monkeypatch):
    from types import SimpleNamespace

    from src.services import dividas as servico

    gravados = {"dividas": [], "pagamentos": []}
    monkeypatch.setattr(servico, "dividas", SimpleNamespace(
        criar_divida=lambda dados: gravados["dividas"].append(dados) or {"id": "novo", **dados},
        registrar_pagamento=lambda dados: gravados["pagamentos"].append(dados) or {"id": "pg", **dados}))
    monkeypatch.setattr(servico, "hoje_br", lambda: date(2026, 11, 4))
    return servico, gravados


def test_criar_divida_simples_serializa_valores_e_nao_confirma_saldo(monkeypatch):
    servico, gravados = _repo_gravador(monkeypatch)
    servico.criar_divida("moto_fiado", "  Nilson ", Decimal("9675.00"))
    d = gravados["dividas"][0]
    assert d["tipo"] == "moto_fiado" and d["credor"] == "Nilson" and d["valor_original"] == "9675.00"
    assert d["saldo_confirmado"] is None and d["confirmado_em"] is None and d["numero_parcelas"] is None


def test_criar_divida_com_saldo_confirmado_marca_a_data_de_hoje(monkeypatch):
    servico, gravados = _repo_gravador(monkeypatch)
    servico.criar_divida("financiamento", "Nicolas", Decimal("21901.92"), 24, Decimal("912.58"), 28, Decimal("20989.34"),
                         "m1", " Financiamento ", " ")
    d = gravados["dividas"][0]
    assert d["saldo_confirmado"] == "20989.34" and d["confirmado_em"] == "2026-11-04" and d["valor_parcela"] == "912.58"
    assert d["dia_vencimento"] == 28 and d["moto_id"] == "m1" and d["descricao"] == "Financiamento" and d["observacoes"] is None


@pytest.mark.parametrize("args,erro", [
    (("compra_parcelada", "X", Decimal("1")), "formulário próprio"),
    (("emprestimo", "  ", Decimal("1")), "credor"),
    (("emprestimo", "X", Decimal("-1")), "negativos"),
    (("emprestimo", "X", Decimal("1"), 10, None), "ou nenhum dos dois"),
])
def test_criar_divida_recusa_dados_invalidos(monkeypatch, args, erro):
    servico, gravados = _repo_gravador(monkeypatch)
    with pytest.raises(ValueError, match=erro):
        servico.criar_divida(*args)
    assert gravados["dividas"] == []


def test_pagar_divida_grava_um_pagamento_sem_parcela(monkeypatch):
    servico, gravados = _repo_gravador(monkeypatch)
    servico.pagar_divida("d1", date(2026, 11, 4), Decimal("300"), "c1", " pix ")
    assert gravados["pagamentos"] == [{"divida_id": "d1", "data": "2026-11-04", "valor": "300", "conta_id": "c1", "observacoes": "pix"}]


def test_pagar_divida_recusa_valor_nao_positivo(monkeypatch):
    servico, gravados = _repo_gravador(monkeypatch)
    with pytest.raises(ValueError, match="positivo"):
        servico.pagar_divida("d1", date(2026, 11, 4), Decimal("0"))
    assert gravados["pagamentos"] == []
