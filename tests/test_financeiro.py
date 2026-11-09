"""Regras do Dashboard financeiro: mês, resultado, caixa, devedores e dívidas."""

from datetime import date
from decimal import Decimal

from src.domain import financeiro


def test_saldo_das_dividas_prefere_o_confirmado_e_separa_motos_fiado():
    r = financeiro.saldo_das_dividas([
        {"tipo": "moto_fiado", "saldo_calculado": "5600", "saldo_confirmado": "3425"},
        {"tipo": "moto_fiado", "saldo_calculado": "1975", "saldo_confirmado": None},
        {"tipo": "emprestimo", "saldo_calculado": "10000", "saldo_confirmado": None},
        {"tipo": "fornecedor", "saldo_calculado": "-50", "saldo_confirmado": None},
    ])
    assert r["moto_fiado"] == Decimal("5400")
    assert r["total"] == Decimal("15400")


def test_entradas_por_conta_junta_as_sem_conta_e_ordena():
    r = financeiro.entradas_por_conta([
        {"conta": "Quezia", "valor": "260"}, {"conta": None, "valor": "2000"}, {"conta": "Luiza", "valor": "865.50"},
        {"conta": None, "valor": "180"}, {"conta": "Quezia", "valor": "40"},
    ])
    assert [l["conta"] for l in r["linhas"]] == ["Sem conta informada", "Luiza", "Quezia"]
    assert r["sem_conta"] == Decimal("2180.00") and r["total"] == Decimal("3345.50")
    assert r["linhas"][0]["proporcao"] == 100 and r["linhas"][2]["proporcao"] == 14


def test_entradas_por_conta_vazia():
    r = financeiro.entradas_por_conta([])
    assert r == {"linhas": [], "total": Decimal("0.00"), "sem_conta": Decimal("0.00")}


def test_despesas_por_categoria_traduz_ordena_e_ignora_zeradas():
    r = financeiro.despesas_por_categoria([
        {"categoria": "manutencao", "valor": "3735"}, {"categoria": "aquisicao", "valor": "7831.09"},
        {"categoria": "seguro_rastreador", "valor": "1212.43"}, {"categoria": "outros", "valor": "0"},
        {"categoria": "manutencao", "valor": "265"}, {"categoria": "coisa_nova", "valor": "10"},
    ])
    assert [l["rotulo"] for l in r["linhas"]] == ["Investimento em veículo", "Manutenção", "Seguro e rastreador", "Coisa nova"]
    assert r["linhas"][1]["valor"] == Decimal("4000.00") and r["total"] == Decimal("13053.52")
    assert r["linhas"][0]["proporcao"] == 100


def test_resultado_por_veiculo_soma_despesas_e_ordena_do_melhor_ao_pior():
    linhas = [
        {"moto_id": "a", "placa": "AAA1A11", "receita_recebida": "1000", "custo_manutencao": "100", "custo_documentos": "50", "custo_despesas": "50"},
        {"moto_id": "b", "placa": "BBB2B22", "receita_recebida": "100", "custo_manutencao": "300", "custo_documentos": None, "custo_despesas": "0"},
        {"moto_id": "c", "placa": None, "receita_recebida": "0", "custo_manutencao": "0", "custo_documentos": "0", "custo_despesas": "0"},
    ]
    r = financeiro.resultado_por_veiculo(linhas, {"a": "JOSE"})
    assert [v["moto_id"] for v in r] == ["a", "c", "b"]
    assert r[0]["despesas"] == Decimal("200.00") and r[0]["resultado"] == Decimal("800.00") and r[0]["locatario"] == "JOSE"
    assert r[1]["placa"] == "—" and r[1]["locatario"] == "—" and r[2]["resultado"] == Decimal("-200.00")


def _meses_grafico():
    return [
        {"mes": date(2026, 9, 1), "receita": Decimal("0"), "despesas": Decimal("450")},
        {"mes": date(2026, 10, 1), "receita": Decimal("14775"), "despesas": Decimal("7387.50")},
    ]


def test_colunas_da_evolucao_usam_a_mesma_escala_e_cabem_no_quadro():
    g = financeiro.colunas_evolucao(_meses_grafico(), largura=600, altura=180)
    assert g["largura"] == 600 and g["altura"] == 208 and g["y_base"] == 180 and len(g["colunas"]) == 2
    out = g["colunas"][1]
    assert out["receita"]["altura"] == 180.0 and out["receita"]["y"] == 0.0
    assert out["despesas"]["altura"] == 90.0
    assert g["colunas"][0]["receita"]["altura"] == 0.0 and g["colunas"][0]["rotulo"] == "set./26"
    for c in g["colunas"]:
        for lado in ("receita", "despesas"):
            r = c[lado]
            assert 0 <= r["x"] and r["x"] + r["largura"] <= 600 and r["y"] + r["altura"] == 180.0


def test_colunas_da_evolucao_sem_valores_ficam_zeradas():
    meses = [{"mes": date(2026, 10, 1), "receita": Decimal("0"), "despesas": Decimal("0")}]
    assert financeiro.colunas_evolucao(meses)["colunas"][0]["receita"]["altura"] == 0.0
    assert financeiro.colunas_evolucao([])["colunas"] == []


def test_consulta_monta_so_o_que_foi_escolhido():
    assert financeiro.consulta() == ""
    assert financeiro.consulta("2026-09") == "?mes=2026-09"
    assert financeiro.consulta("2026-09", True, True) == "?mes=2026-09&compacto=1&ocultar=1"
    assert financeiro.consulta(None, False, True) == "?ocultar=1"


def test_opcao_ligada_so_com_1():
    assert financeiro.opcao_ligada("1") and not financeiro.opcao_ligada(None) and not financeiro.opcao_ligada("true")


def test_aba_do_painel_aceita_so_as_tres_e_cai_em_hoje():
    assert [financeiro.aba_do_painel(x) for x in ("hoje", "dinheiro", "frota")] == ["hoje", "dinheiro", "frota"]
    for ruim in (None, "", "Dinheiro", "relatorios", "hoje; drop"):
        assert financeiro.aba_do_painel(ruim) == "hoje"


def test_consulta_leva_a_aba_so_quando_nao_e_a_padrao():
    assert financeiro.consulta(aba="hoje") == "" and financeiro.consulta(aba="dinheiro") == "?aba=dinheiro"
    assert financeiro.consulta("2026-09", True, True, "dinheiro") == "?aba=dinheiro&mes=2026-09&compacto=1&ocultar=1"


def test_links_do_painel_mantem_o_que_esta_ligado():
    l = financeiro.links_do_painel("2026-10", "2026-09", None, compacto=True, ocultar=False, aba="dinheiro")
    assert l["anterior"] == "?aba=dinheiro&mes=2026-09&compacto=1" and l["seguinte"] is None and l["atual"] == "?aba=dinheiro&compacto=1"
    assert l["compacto"] == "?aba=dinheiro&mes=2026-10" and l["ocultar"] == "?aba=dinheiro&mes=2026-10&compacto=1&ocultar=1"
    assert l["abas"] == {"hoje": "?compacto=1", "dinheiro": "?aba=dinheiro&compacto=1", "frota": "?aba=frota&compacto=1"}
    assert financeiro.links_do_painel("2026-08", "2026-07", "2026-09", False, True, "dinheiro")["seguinte"] == "?aba=dinheiro&mes=2026-09&ocultar=1"


def test_links_fora_da_aba_dinheiro_nao_tem_navegacao_de_mes():
    l = financeiro.links_do_painel(None, None, None, False, True, "hoje")
    assert l["anterior"] is None and l["seguinte"] is None and l["compacto"] == "?compacto=1&ocultar=1" and l["ocultar"] == ""
    assert l["abas"]["hoje"] == "?ocultar=1"
