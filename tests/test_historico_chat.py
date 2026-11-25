"""Testes de src/domain/historico_chat.py (histórico dos chats entregue pelo conector)."""

from datetime import date

import pytest

from src.domain.historico_chat import (
    MAXIMO_REGISTROS_POR_LOTE,
    lacunas,
    normalizar_dados,
    normalizar_lote,
    normalizar_registro,
    periodos_cobertos,
    resumo_do_registro,
)

HOJE = date(2026, 11, 25)


def _registro(**extra):
    return {"tipo": "pagamento", "data": "2026-10-12", "dados": {"cliente": "Jhonatan Silva", "placa": "abc-1d23", "valor": "275"},
            "trecho": "12/10 Jhonatan pagou 275", **extra}


def _lote(**extra):
    return {"fonte": "chat_financeiro", "rotulo": "financeiro-out", "periodo_inicio": "2026-10-01", "periodo_fim": "2026-10-31",
            "registros": [_registro()], **extra}


class TestNormalizarDados:
    def test_normaliza_dinheiro_placa_e_cpf(self):
        d = normalizar_dados({"Valor": "1.234,56", "Placa": "abc-1d23", "CPF": "529.982.247-25", "Cliente": "  Maria   Silva ", "Forma Pgto": "Pix",
                              "pago": True, "parcela": 3, "vazio": "", "nulo": None})
        assert d == {"valor": "1234.56", "placa": "ABC1D23", "cpf": "52998224725", "cliente": "Maria Silva", "forma_pgto": "Pix", "pago": True,
                     "parcela": 3}

    def test_numero_vira_dinheiro_nas_chaves_de_valor(self):
        assert normalizar_dados({"valor": 275.5, "saldo": 100})["valor"] == "275.50" and normalizar_dados({"saldo": 100})["saldo"] == "100.00"

    @pytest.mark.parametrize("dados,trecho", [({}, "objeto"), (None, "objeto"), ("x", "objeto"), ({"valor": "-5"}, "valor em reais"), ({"valor": "abc"}, "valor em reais"),
                                              ({"placa": "123"}, "placa inválida"), ({"cpf": "123"}, "11 dígitos"), ({"a": {"b": 1}}, "valor simples"),
                                              ({"a": [1]}, "valor simples"), ({"a": ""}, "vazios"), ({"x": "y" * 150, "z": "w" * 150, "q": "v" * 200, "r": "u" * 200,
                                                                                                     "s": "t" * 200, "t": "s" * 200, "u": "r" * 200, "v": "q" * 200,
                                                                                                     "w": "p" * 200, "y": "o" * 200, "aa": "n" * 200}, "passam de 2000")])
    def test_recusa(self, dados, trecho):
        with pytest.raises(ValueError, match=trecho):
            normalizar_dados(dados)

    def test_texto_longo_e_cortado(self):
        assert len(normalizar_dados({"descricao": "x" * 500})["descricao"]) == 200


class TestResumo:
    def test_pagamento(self):
        d = normalizar_dados({"cliente": "Jhonatan Silva", "valor": 275})
        assert resumo_do_registro("pagamento", d, date(2026, 10, 12)) == "Pagamento de Jhonatan Silva R$ 275,00 em 12/10/2026"

    def test_despesa_multa_cliente_veiculo_contrato(self):
        assert resumo_do_registro("despesa", normalizar_dados({"placa": "ABC1D23", "valor": 95, "descricao": "pastilha"}), date(2026, 10, 1)) \
            == "Despesa (ABC1D23) R$ 95,00 em 01/10/2026 pastilha"
        assert resumo_do_registro("multa", normalizar_dados({"placa": "ABC1D23", "ait": "X123", "valor": 130.16}), None) == "Multa ABC1D23 AIT X123 R$ 130,16"
        assert resumo_do_registro("cliente", normalizar_dados({"nome": "Maria Silva", "cpf": "52998224725"}), None) == "Cliente Maria Silva (CPF final 4725)"
        assert resumo_do_registro("veiculo", normalizar_dados({"placa": "ABC1D23", "marca": "Honda", "modelo": "CG"}), None) == "Veículo ABC1D23 Honda CG"
        assert resumo_do_registro("contrato", normalizar_dados({"cliente": "Maria", "placa": "ABC1D23", "valor_periodo": 275, "periodicidade": "semanal"}),
                                  date(2026, 9, 1)) == "Contrato Maria / ABC1D23 R$ 275,00 semanal desde 01/09/2026"

    def test_tipo_livre_mostra_os_primeiros_campos_sem_cpf(self):
        r = resumo_do_registro("divida", normalizar_dados({"credor": "Lima", "saldo": 1000, "cpf": "52998224725"}), None)
        assert r.startswith("Divida") and "credor=Lima" in r and "52998224725" not in r

    def test_corta_em_200(self):
        assert len(resumo_do_registro("despesa", normalizar_dados({"descricao": "d" * 200, "valor": 1}), None)) <= 200


class TestRegistro:
    def test_registro_valido(self):
        r = normalizar_registro(_registro(), "chat_financeiro", HOJE)
        assert r["tipo"] == "pagamento" and r["data"] == "2026-10-12" and r["dados"]["placa"] == "ABC1D23" and r["dados"]["valor"] == "275.00"
        assert r["trecho"] == "12/10 Jhonatan pagou 275" and r["resumo"].startswith("Pagamento de Jhonatan Silva")

    def test_data_em_formato_br_e_sem_data(self):
        assert normalizar_registro(_registro(data="12/10/2026"), "chat_financeiro", HOJE)["data"] == "2026-10-12"
        assert normalizar_registro(_registro(data=None), "chat_financeiro", HOJE)["data"] is None

    @pytest.mark.parametrize("campos,trecho", [({"tipo": "lazer"}, "tipo precisa"), ({"trecho": ""}, "trecho do chat"), ({"data": "ontem"}, "formato"),
                                               ({"data": "2027-01-01"}, "futuro"), ({"data": "1990-01-01"}, "ano inválido"), ({"dados": {"valor": "-1"}}, "valor")])
    def test_recusa(self, campos, trecho):
        with pytest.raises(ValueError, match=trecho):
            normalizar_registro(_registro(**campos), "chat_financeiro", HOJE)

    def test_trecho_longo_e_cortado(self):
        assert len(normalizar_registro(_registro(trecho="t" * 900), "chat_financeiro", HOJE)["trecho"]) == 600

    def test_nao_e_objeto(self):
        with pytest.raises(ValueError, match="objeto"):
            normalizar_registro("texto", "chat_financeiro", HOJE)


class TestLote:
    def test_lote_valido(self):
        r = normalizar_lote(_lote(observacao="  lido até 31/10 "), HOJE)
        assert r["fonte"] == "chat_financeiro" and r["rotulo"] == "financeiro-out" and r["observacao"] == "lido até 31/10" and len(r["registros"]) == 1

    @pytest.mark.parametrize("campos,trecho", [({"fonte": "outro"}, "fonte"), ({"rotulo": ""}, "rótulo"), ({"rotulo": "r" * 61}, "rótulo"),
                                               ({"periodo_inicio": ""}, "início do período"), ({"periodo_fim": "2026-09-30"}, "antes do início"),
                                               ({"periodo_inicio": "2020-01-01", "periodo_fim": "2026-10-31"}, "passa de 1100 dias"),
                                               ({"registros": []}, "ao menos um"), ({"registros": "x"}, "ao menos um"),
                                               ({"registros": [_registro()] * (MAXIMO_REGISTROS_POR_LOTE + 1)}, "no máximo 50"),
                                               ({"observacao": "o" * 501}, "observação")])
    def test_recusa(self, campos, trecho):
        with pytest.raises(ValueError, match=trecho):
            normalizar_lote(_lote(**campos), HOJE)

    def test_tudo_ou_nada_com_o_numero_de_cada_erro(self):
        registros = [_registro(), _registro(tipo="xx"), _registro(trecho=""), _registro(data="2026-12-01")]
        with pytest.raises(ValueError) as erro:
            normalizar_lote(_lote(registros=registros, periodo_fim="2026-11-25"), HOJE)
        texto = str(erro.value)
        assert texto.startswith("Nenhum registro foi enviado") and "registro 2:" in texto and "registro 3:" in texto and "registro 4:" in texto
        assert "registro 1:" not in texto

    def test_data_fora_do_periodo_do_lote(self):
        with pytest.raises(ValueError, match="fora do período do lote"):
            normalizar_lote(_lote(registros=[_registro(data="2026-09-30")]), HOJE)

    def test_so_mostra_os_primeiros_erros(self):
        with pytest.raises(ValueError, match=r"\(e mais 3\)"):
            normalizar_lote(_lote(registros=[_registro(tipo="xx")] * 8), HOJE)


class TestCobertura:
    def test_junta_periodos_que_se_tocam_ou_se_sobrepoem(self):
        faixas = periodos_cobertos([("2026-10-10", "2026-10-20"), ("2026-10-01", "2026-10-12"), ("2026-10-21", "2026-10-31")])
        assert faixas == [(date(2026, 10, 1), date(2026, 10, 31))]

    def test_mantem_separadas_as_faixas_com_buraco(self):
        lotes = [("2026-08-01", "2026-08-31"), ("2026-10-01", "2026-10-31"), ("2026-09-05", "2026-09-10")]
        assert periodos_cobertos(lotes) == [(date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 9, 5), date(2026, 9, 10)), (date(2026, 10, 1), date(2026, 10, 31))]
        assert lacunas(lotes) == [(date(2026, 9, 1), date(2026, 9, 4)), (date(2026, 9, 11), date(2026, 9, 30))]

    def test_sem_buracos_e_sem_lotes(self):
        assert lacunas([("2026-10-01", "2026-10-31")]) == [] and lacunas([]) == [] and periodos_cobertos([]) == []

    def test_aceita_datas_ja_convertidas(self):
        assert lacunas([(date(2026, 1, 1), date(2026, 1, 5)), (date(2026, 1, 8), date(2026, 1, 9))]) == [(date(2026, 1, 6), date(2026, 1, 7))]
