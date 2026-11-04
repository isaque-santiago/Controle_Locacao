"""Regras do Dashboard financeiro: mês, resultado, caixa, devedores e dívidas."""

from datetime import date
from decimal import Decimal

from src.domain import financeiro


def _cobranca(contrato="c1", cliente="cl1", moto="m1", tipo="locacao", saldo="100", vencimento="2026-11-01",
              situacao="atrasada"):
    return {"contrato_id": contrato, "cliente_id": cliente, "moto_id": moto, "tipo": tipo, "saldo": saldo,
            "vencimento": vencimento, "situacao": situacao}


def test_mes_da_consulta_aceita_aaaa_mm():
    assert financeiro.mes_da_consulta("2026-09", date(2026, 11, 4)) == date(2026, 9, 1)


def test_mes_da_consulta_invalido_vazio_ou_futuro_vale_o_mes_de_hoje():
    hoje = date(2026, 11, 4)
    for texto in (None, "", "lixo", "2026-13", "2026-00", "2027-01", "2026-9-1"):
        assert financeiro.mes_da_consulta(texto, hoje) == date(2026, 11, 1)


def test_somar_meses_atravessa_o_ano():
    assert financeiro.somar_meses(date(2026, 11, 1), 2) == date(2027, 1, 1)
    assert financeiro.somar_meses(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert financeiro.somar_meses(date(2026, 11, 1), 0) == date(2026, 11, 1)


def test_rotulos_do_mes():
    assert financeiro.rotulo_mes(date(2026, 11, 1)) == "novembro de 2026"
    assert financeiro.rotulo_mes_curto(date(2026, 6, 1)) == "jun./26"


def test_consolidar_mes_calcula_resultado_e_caixa():
    mes = financeiro.consolidar_mes({
        "mes": "2026-10-01", "receita": "14775.00", "despesas": "10000", "investimento": 2000,
        "parcelas_divida": "1864.24", "retiradas": "2022", "aportes": "500",
    })
    assert mes["mes"] == date(2026, 10, 1)
    assert mes["resultado"] == Decimal("4775.00")
    # 4775 - 2000 - 1864,24 - 2022 + 500
    assert mes["caixa"] == Decimal("-611.24")
    assert mes["margem"] == 32


def test_consolidar_mes_vazio_zera_tudo_e_margem_nula():
    mes = financeiro.consolidar_mes({"mes": "2026-06-01"})
    assert mes["receita"] == mes["resultado"] == mes["caixa"] == Decimal("0.00")
    assert mes["margem"] is None


def test_margem_negativa_e_arredondada():
    assert financeiro.margem(Decimal("3445.50"), Decimal("-1715.70")) == -50
    assert financeiro.margem(Decimal("0"), Decimal("-10")) is None


def test_receita_mensal_estimada_so_dos_contratos_ativos_pela_periodicidade():
    contratos = [
        {"status": "ativo", "periodicidade": "semanal", "valor_periodo": "1200"},
        {"status": "ativo", "periodicidade": "mensal", "valor_periodo": "500"},
        {"status": "ativo", "periodicidade": "quinzenal", "valor_periodo": "600"},
        {"status": "encerrado", "periodicidade": "semanal", "valor_periodo": "9999"},
        {"status": "ativo", "periodicidade": "desconhecida", "valor_periodo": "70"},
    ]
    # 1200 x 52/12 + 500 + 600 x 26/12
    assert financeiro.receita_mensal_estimada(contratos) == Decimal("5200.00") + Decimal("500") + Decimal("1300.00")
    assert financeiro.receita_mensal_estimada([]) == Decimal("0.00")


def test_faixa_de_atraso_corta_em_15_dias():
    assert financeiro.faixa_de_atraso(14) == "em_atraso"
    assert financeiro.faixa_de_atraso(15) == "inadimplente"
    assert financeiro.faixa_de_atraso(9, corte=7) == "inadimplente"


def test_devedores_somam_debito_encargos_e_usam_o_maior_atraso():
    hoje = date(2026, 11, 10)
    r = financeiro.analisar_devedores(
        [_cobranca(saldo="100", vencimento="2026-11-03"), _cobranca(saldo="50", vencimento="2026-11-08")],
        {"cl1": "JOSE"}, {"m1": "POU7015"}, Decimal("15"), Decimal("7"), hoje,
    )
    # 7 dias: 15 + 49 = 64; 2 dias: 15 + 14 = 29
    assert r["a_receber"] == Decimal("150")
    assert r["encargos"] == Decimal("93.00")
    linha = r["ranking"][0]
    assert (linha["cliente"], linha["placa"], linha["dias_atraso"]) == ("JOSE", "POU7015", 7)
    assert linha["total"] == Decimal("243.00") and linha["faixa"] == "em_atraso"
    assert r["contratos_em_aberto"] == 1 and r["em_atraso"] == 1 and r["inadimplentes"] == 0


def test_devedores_ignoram_o_que_nao_esta_atrasado_ou_sem_saldo():
    hoje = date(2026, 11, 10)
    r = financeiro.analisar_devedores(
        [_cobranca(situacao="aberta"), _cobranca(situacao="paga"), _cobranca(situacao="cancelada"),
         _cobranca(saldo="0")],
        {}, {}, Decimal("15"), Decimal("7"), hoje,
    )
    assert r["contratos_em_aberto"] == 0 and r["a_receber"] == Decimal("0") and r["ranking"] == []


def test_encargos_so_incidem_sobre_locacao():
    hoje = date(2026, 11, 10)
    r = financeiro.analisar_devedores(
        [_cobranca(tipo="multa_transito", saldo="200", vencimento="2026-11-01")],
        {}, {}, Decimal("15"), Decimal("7"), hoje,
    )
    assert r["a_receber"] == Decimal("200") and r["encargos"] == Decimal("0.00")


def test_ranking_ordena_por_total_conta_faixas_e_limita():
    hoje = date(2026, 11, 30)
    cobrancas = [
        _cobranca(contrato="a", cliente="x", moto="1", saldo="100", vencimento="2026-11-25"),
        _cobranca(contrato="b", cliente="y", moto="2", saldo="100", vencimento="2026-11-01"),
        _cobranca(contrato="c", cliente="z", moto="3", saldo="900", vencimento="2026-11-29"),
    ]
    r = financeiro.analisar_devedores(cobrancas, {"x": "X", "y": "Y", "z": "Z"}, {}, Decimal("15"), Decimal("7"),
                                      hoje, limite=2)
    assert [l["cliente"] for l in r["ranking"]] == ["Z", "Y"]
    assert r["contratos_em_aberto"] == 3 and r["em_atraso"] == 2 and r["inadimplentes"] == 1
    assert r["ranking"][0]["placa"] == "—"


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


def _devedores(inad=0, atraso=0, receber="0", encargos="0"):
    return {"inadimplentes": inad, "em_atraso": atraso, "a_receber": Decimal(receber), "encargos": Decimal(encargos)}


def _mes(caixa="0", retiradas="0", aportes="0"):
    return {"caixa": Decimal(caixa), "retiradas": Decimal(retiradas), "aportes": Decimal(aportes)}


def test_alertas_criticos_e_de_atencao():
    a = {x["titulo"]: x for x in financeiro.alertas_financeiros(
        _devedores(inad=3, atraso=6, receber="6849", encargos="1003"), _mes(caixa="-1715.70", retiradas="50", aportes="10"),
        Decimal("115"), Decimal("2180"), 1)}
    assert a["Contratos inadimplentes (15 dias ou mais)"]["tom"] == "perigo" and a["Contratos inadimplentes (15 dias ou mais)"]["status"] == "Crítico"
    assert a["Contratos em atraso (até 14 dias)"]["tom"] == "atencao"
    assert a["Caixa do mês"]["tom"] == "perigo" and a["Caixa do mês"]["formato"] == "moeda"
    assert a["Total a cobrar (débito + encargos)"]["valor"] == Decimal("7852")
    assert a["Retiradas no mês"]["tom"] == "atencao" and a["Aportes de fora no mês"]["tom"] == "info"
    assert a["Motos em manutenção"]["valor"] == 1 and a["Motos em manutenção"]["formato"] == "qtd"


def test_alertas_ficam_ok_quando_nao_ha_o_que_avisar():
    alertas = financeiro.alertas_financeiros(_devedores(), _mes(caixa="100"), Decimal("0"), Decimal("0"), 0)
    assert [a["tom"] for a in alertas] == ["ok"] * 8 + ["info"]
    assert all(a["status"] == "OK" for a in alertas[:8])


def _meses_grafico():
    return [
        {"mes": date(2026, 9, 1), "receita": Decimal("0"), "despesas": Decimal("450")},
        {"mes": date(2026, 10, 1), "receita": Decimal("14775"), "despesas": Decimal("7387.50")},
    ]


def test_colunas_da_evolucao_usam_a_mesma_escala_e_cabem_no_quadro():
    g = financeiro.colunas_evolucao(_meses_grafico(), largura=600, altura=180)
    assert g["largura"] == 600 and g["altura"] == 208 and len(g["colunas"]) == 2
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
