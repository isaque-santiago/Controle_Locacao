"""Serviço do Dashboard: as três abas (Hoje, Dinheiro e Frota) leem das mesmas fontes."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.services import financeiro

HOJE = date(2026, 11, 10)


def _meses(ate: date):
    out = []
    for i in range(5, -1, -1):
        indice = ate.year * 12 + ate.month - 1 - i
        out.append({"mes": date(indice // 12, indice % 12 + 1, 1).isoformat(), "receita": "100", "despesas": "40",
                    "investimento": "20", "parcelas_divida": "10", "retiradas": "5", "aportes": "0"})
    return out


def _preparar(monkeypatch, config=None, falha_em=None):
    pedidos = {"resumo": [], "detalhe": []}

    def resumo(mes, quantidade):
        pedidos["resumo"].append((mes, quantidade))
        return _meses(mes)[-quantidade:]

    def detalhe(mes):
        pedidos["detalhe"].append(mes)
        if falha_em == "detalhe":
            raise RuntimeError("function rpc_detalhe_financeiro does not exist")
        return {
            "entradas_por_conta": [{"conta": "Quezia", "valor": "260"}, {"conta": None, "valor": "40"}],
            "despesas_por_categoria": [{"categoria": "manutencao", "valor": "25"}, {"categoria": "aquisicao", "valor": "300"}],
            "a_repassar": "115", "receita_semana": "70",
        }

    monkeypatch.setattr(financeiro, "repositorio", SimpleNamespace(
        resumo_mensal=resumo, detalhe_mensal=detalhe,
        saldos_dividas=lambda: [{"tipo": "moto_fiado", "saldo_calculado": "300", "saldo_confirmado": None}],
        parcelas_de_divida=lambda: [{"situacao": "atrasada", "saldo": "1000"}, {"situacao": "a_vencer", "saldo": "1000"}],
        resultado_por_veiculo=lambda: [{"moto_id": "m1", "placa": "POU7015", "receita_recebida": "100", "custo_manutencao": "25",
                                        "custo_documentos": "0", "custo_despesas": "0"}],
    ))
    monkeypatch.setattr(financeiro, "configuracoes", SimpleNamespace(obter=lambda: config or {"multa_atraso_valor": "15", "encargo_diario_valor": "7"}))
    monkeypatch.setattr(financeiro, "clientes", SimpleNamespace(listar=lambda: [{"id": "cl1", "nome": "JOSE"}]))
    monkeypatch.setattr(financeiro, "motos", SimpleNamespace(listar=lambda: [
        {"id": "m1", "placa": "POU7015", "status": "alugada"}, {"id": "m2", "placa": "OSL8828", "status": "disponivel"},
        {"id": "m3", "placa": "PMP2B63", "status": "manutencao"}]))
    monkeypatch.setattr(financeiro, "cobrancas", SimpleNamespace(listar=lambda: [
        {"id": "k1", "contrato_id": "c1", "cliente_id": "cl1", "moto_id": "m1", "tipo": "locacao", "saldo": "100", "valor": "100",
         "vencimento": "2026-11-01", "situacao": "atrasada"},
        {"id": "k2", "contrato_id": "c1", "cliente_id": "cl1", "moto_id": "m1", "tipo": "locacao", "saldo": "280", "valor": "280",
         "vencimento": "2026-11-10", "situacao": "aberta"}]))
    monkeypatch.setattr(financeiro, "contratos", SimpleNamespace(listar=lambda: [
        {"status": "ativo", "periodicidade": "mensal", "valor_periodo": "500", "moto_id": "m1", "cliente_id": "cl1"}]))
    return pedidos


# ------------------------------------------------------------------------------------------------ Hoje --


def test_painel_hoje_traz_cobranca_frota_caixa_e_atencao(monkeypatch):
    pedidos = _preparar(monkeypatch)

    p = financeiro.painel_hoje(HOJE)

    assert pedidos["resumo"] == [(date(2026, 11, 1), 6)] and pedidos["detalhe"] == [date(2026, 11, 1)]
    cobranca = p["cobranca"]
    # 9 dias de atraso na k1 (15 + 7 x 9 = 78) e a multa do dia na k2 (15)
    assert cobranca["total_linhas"] == 1 and cobranca["linhas"][0]["cliente"] == "JOSE" and cobranca["linhas"][0]["placa"] == "POU7015"
    assert cobranca["em_atraso"] == Decimal("100") and cobranca["vencem_hoje"] == Decimal("280") and cobranca["a_cobrar"] == Decimal("380")
    assert cobranca["encargos"] == Decimal("93.00") and cobranca["linhas"][0]["cobranca_id"] == "k1"
    assert p["frota"] == {"total": 3, "contagem": {"alugada": 1, "disponivel": 1, "manutencao": 1, "inativa": 0}, "ativas": 3, "ocupacao": 33}
    assert p["caixa"]["valor"] == Decimal("25.00") and p["caixa"]["investimento"] == Decimal("20.00")  # 100 - 40 - 20 - 10 - 5
    assert p["caixa"]["serie"]["final"] == Decimal("25.00") and len(p["caixa"]["serie"]["pontos"].split()) == 6
    assert [f["contratos"] for f in cobranca["faixas_atraso"]] == [0, 1, 0, 0]  # 9 dias de atraso: faixa de 7 a 14
    titulos = [i.titulo for i in p["atencao_financeira"]]
    assert titulos == ["Parcela de dívida atrasada", "Despesa a repassar ao locatário", "Entrada do mês sem conta"]
    assert p["faixas"] == {"em_atraso": "até 14 dias", "inadimplente": "15 dias ou mais"} and p["mes_texto"] == "2026-11"


def test_painel_hoje_usa_o_corte_das_configuracoes_e_cai_em_15_sem_a_coluna(monkeypatch):
    _preparar(monkeypatch, config={"multa_atraso_valor": "15", "encargo_diario_valor": "7", "dias_inadimplencia": 7})
    p = financeiro.painel_hoje(HOJE)
    assert p["cobranca"]["contratos_inadimplentes"] == 1 and p["faixas"]["inadimplente"] == "7 dias ou mais"
    _preparar(monkeypatch)
    assert financeiro.painel_hoje(HOJE)["cobranca"]["contratos_em_atraso"] == 1


def test_se_so_o_dinheiro_falhar_a_aba_hoje_ainda_mostra_quem_cobrar_e_a_frota(monkeypatch, caplog):
    _preparar(monkeypatch, falha_em="detalhe")
    with caplog.at_level("ERROR"):
        p = financeiro.painel_hoje_seguro(HOJE)
    assert "indisponivel" not in p and p["caixa"] is None and p["atencao_financeira"] == []
    assert p["cobranca"]["total_linhas"] == 1 and p["frota"]["total"] == 3 and "caixa do mês" in caplog.text


def test_painel_hoje_seguro_avisa_so_se_cobranca_ou_frota_falharem(monkeypatch, caplog):
    _preparar(monkeypatch)
    monkeypatch.setattr(financeiro.cobrancas, "listar", lambda: (_ for _ in ()).throw(RuntimeError("banco fora do ar")))
    with caplog.at_level("ERROR"):
        p = financeiro.painel_hoje_seguro(HOJE)
    assert p == {"mes_texto": "2026-11", "indisponivel": True} and "aba Hoje" in caplog.text


# -------------------------------------------------------------------------------------------- Dinheiro --


def test_painel_dinheiro_do_mes_atual(monkeypatch):
    pedidos = _preparar(monkeypatch)

    p = financeiro.painel_dinheiro(None, HOJE)

    assert pedidos["resumo"] == [(date(2026, 11, 1), 6)]
    assert p["mes_texto"] == "2026-11" and p["mes_rotulo"] == "novembro de 2026" and p["e_mes_atual"]
    assert p["mes_anterior"] == "2026-10" and p["mes_seguinte"] is None and p["mes_maximo"] == "2026-11"
    assert p["atual"]["mes"] == date(2026, 11, 1) and p["atual"]["resultado"] == Decimal("60.00") and p["atual"]["caixa"] == Decimal("25.00")
    assert [m["rotulo"] for m in p["evolucao"]] == ["jun./26", "jul./26", "ago./26", "set./26", "out./26", "nov./26"]
    assert len(p["grafico"]["colunas"]) == 6
    # previsto: as cobranças que vencem em novembro (100 + 280); a receita do mês é a mesma da aba Hoje (R$ 100)
    assert p["previsto"] == Decimal("380") and p["percentual_previsto"] == 26
    assert p["esperado_ate_hoje"] == Decimal("380") and p["percentual_esperado"] == 100 and p["variacoes"] is None  # mês corrente: sem variação
    assert p["dividas"]["total"] == Decimal("300") and p["receita_estimada"] == Decimal("500.00") and p["receita_semana"] == Decimal("70")
    assert [l["conta"] for l in p["entradas"]["linhas"]] == ["Quezia", "Sem conta informada"]
    assert p["categorias"]["linhas"][0]["rotulo"] == "Investimento em veículo"


def test_painel_dinheiro_de_mes_passado_oferece_o_seguinte_e_mes_invalido_volta_ao_atual(monkeypatch):
    pedidos = _preparar(monkeypatch)
    p = financeiro.painel_dinheiro("2026-08", HOJE)
    assert pedidos["resumo"] == [(date(2026, 8, 1), 6)] and not p["e_mes_atual"]
    assert p["mes_seguinte"] == "2026-09" and p["mes_anterior"] == "2026-07"
    assert p["variacoes"]["receita"]["tom"] == "neutro" and "Igual" in p["variacoes"]["receita"]["texto"]  # mês fechado: compara com o anterior
    assert financeiro.painel_dinheiro("2030-01", HOJE)["mes_texto"] == "2026-11"
    assert financeiro.painel_dinheiro("abc", HOJE)["mes_texto"] == "2026-11"


def test_painel_dinheiro_seguro_guarda_a_navegacao_do_mes(monkeypatch, caplog):
    _preparar(monkeypatch, falha_em="detalhe")
    with caplog.at_level("ERROR"):
        p = financeiro.painel_dinheiro_seguro("2026-08", HOJE)
    assert p["indisponivel"] is True and p["mes_texto"] == "2026-08" and p["mes_anterior"] == "2026-07"
    assert p["mes_seguinte"] == "2026-09" and p["mes_rotulo"] == "agosto de 2026" and "atual" not in p
    assert "aba Dinheiro" in caplog.text


# ---------------------------------------------------------------------------------------------- Frota --


def test_painel_frota_traz_veiculos_e_o_gasto_com_manutencao_da_mesma_fonte_do_dinheiro(monkeypatch):
    _preparar(monkeypatch)
    p = financeiro.painel_frota(HOJE)
    assert p["veiculos"][0]["placa"] == "POU7015" and p["veiculos"][0]["locatario"] == "JOSE" and p["veiculos"][0]["resultado"] == Decimal("75.00")
    assert p["manutencao_mes"] == Decimal("25.00") and p["mes_rotulo"] == "novembro de 2026"
    # a categoria Manutenção da aba Dinheiro mostra o mesmo valor
    manut_dinheiro = next(c["valor"] for c in financeiro.painel_dinheiro(None, HOJE)["categorias"]["linhas"] if c["categoria"] == "manutencao")
    assert manut_dinheiro == p["manutencao_mes"]


def test_painel_frota_sem_manutencao_no_mes_mostra_zero(monkeypatch):
    _preparar(monkeypatch)
    monkeypatch.setattr(financeiro.repositorio, "detalhe_mensal", lambda mes: {
        "entradas_por_conta": [], "despesas_por_categoria": [{"categoria": "outros", "valor": "5"}], "a_repassar": "0", "receita_semana": "0"})
    assert financeiro.painel_frota(HOJE)["manutencao_mes"] == Decimal("0.00")


def test_painel_frota_seguro(monkeypatch, caplog):
    _preparar(monkeypatch, falha_em="detalhe")
    with caplog.at_level("ERROR"):
        assert financeiro.painel_frota_seguro(HOJE) == {"indisponivel": True}


# -------------------------------------------------------------------------------- uma definição só --


def test_o_caixa_da_aba_hoje_e_o_da_aba_dinheiro_sao_o_mesmo_numero(monkeypatch):
    _preparar(monkeypatch)
    assert financeiro.painel_hoje(HOJE)["caixa"]["valor"] == financeiro.painel_dinheiro(None, HOJE)["atual"]["caixa"]
