"""Serviço do dashboard financeiro: junta o resumo mensal, os devedores e as dívidas."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.services import financeiro


def _meses(ate: date):
    out = []
    for i in range(5, -1, -1):
        indice = ate.year * 12 + ate.month - 1 - i
        out.append({"mes": date(indice // 12, indice % 12 + 1, 1).isoformat(), "receita": "100", "despesas": "40",
                    "investimento": "0", "parcelas_divida": "10", "retiradas": "5", "aportes": "0"})
    return out


def _preparar(monkeypatch, pedidos=None):
    def resumo(mes, quantidade):
        if pedidos is not None:
            pedidos.append((mes, quantidade))
        return _meses(mes)

    monkeypatch.setattr(financeiro, "repositorio", SimpleNamespace(
        resumo_mensal=resumo,
        saldos_dividas=lambda: [{"tipo": "moto_fiado", "saldo_calculado": "300", "saldo_confirmado": None}],
        detalhe_mensal=lambda mes: {
            "entradas_por_conta": [{"conta": "Quezia", "valor": "260"}, {"conta": None, "valor": "40"}],
            "despesas_por_categoria": [{"categoria": "manutencao", "valor": "25"}],
            "a_repassar": "115", "receita_semana": "70",
        },
        resultado_por_veiculo=lambda: [
            {"moto_id": "m1", "placa": "POU7015", "receita_recebida": "100", "custo_manutencao": "25",
             "custo_documentos": "0", "custo_despesas": "0"}],
    ))
    monkeypatch.setattr(financeiro, "configuracoes", SimpleNamespace(
        obter=lambda: {"multa_atraso_valor": "15", "encargo_diario_valor": "7"}))
    monkeypatch.setattr(financeiro, "clientes", SimpleNamespace(listar=lambda: [{"id": "cl1", "nome": "JOSE"}]))
    monkeypatch.setattr(financeiro, "motos", SimpleNamespace(listar=lambda: [{"id": "m1", "placa": "POU7015", "status": "manutencao"}]))
    monkeypatch.setattr(financeiro, "cobrancas", SimpleNamespace(listar=lambda: [
        {"contrato_id": "c1", "cliente_id": "cl1", "moto_id": "m1", "tipo": "locacao", "saldo": "100",
         "vencimento": "2026-11-01", "situacao": "atrasada"}]))
    monkeypatch.setattr(financeiro, "contratos", SimpleNamespace(listar=lambda: [
        {"status": "ativo", "periodicidade": "mensal", "valor_periodo": "500", "moto_id": "m1", "cliente_id": "cl1"}]))


def test_painel_do_mes_atual(monkeypatch):
    pedidos = []
    _preparar(monkeypatch, pedidos)

    p = financeiro.painel(None, hoje=date(2026, 11, 4))

    assert pedidos == [(date(2026, 11, 1), 6)]
    assert p["mes_texto"] == "2026-11" and p["mes_rotulo"] == "novembro de 2026" and p["e_mes_atual"]
    assert p["mes_anterior"] == "2026-10" and p["mes_seguinte"] is None and p["mes_maximo"] == "2026-11"
    assert p["atual"]["mes"] == date(2026, 11, 1) and p["atual"]["resultado"] == Decimal("60.00")
    assert p["atual"]["caixa"] == Decimal("45.00")
    assert p["anterior"]["mes"] == date(2026, 10, 1)
    assert [m["rotulo"] for m in p["evolucao"]] == ["jun./26", "jul./26", "ago./26", "set./26", "out./26", "nov./26"]
    # 3 dias de atraso na cobrança de 01/11 vista em 04/11: 15 + 7 x 3
    assert p["devedores"]["a_receber"] == Decimal("100") and p["devedores"]["encargos"] == Decimal("36.00")
    assert p["devedores"]["ranking"][0]["cliente"] == "JOSE"
    assert p["dividas"]["total"] == Decimal("300") and p["receita_estimada"] == Decimal("500.00")


def test_painel_de_mes_passado_oferece_o_seguinte(monkeypatch):
    pedidos = []
    _preparar(monkeypatch, pedidos)

    p = financeiro.painel("2026-08", hoje=date(2026, 11, 4))

    assert pedidos == [(date(2026, 8, 1), 6)]
    assert not p["e_mes_atual"] and p["mes_seguinte"] == "2026-09" and p["mes_anterior"] == "2026-07"


def test_painel_com_mes_invalido_volta_ao_mes_atual(monkeypatch):
    _preparar(monkeypatch)
    assert financeiro.painel("2030-01", hoje=date(2026, 11, 4))["mes_texto"] == "2026-11"
    assert financeiro.painel("abc", hoje=date(2026, 11, 4))["mes_texto"] == "2026-11"


def test_painel_traz_os_detalhes_da_etapa_2(monkeypatch):
    _preparar(monkeypatch)

    p = financeiro.painel(None, hoje=date(2026, 11, 4))

    assert [l["conta"] for l in p["entradas"]["linhas"]] == ["Quezia", "Sem conta informada"]
    assert p["entradas"]["sem_conta"] == Decimal("40.00")
    assert p["categorias"]["linhas"][0]["rotulo"] == "Manutenção" and p["categorias"]["total"] == Decimal("25.00")
    assert p["receita_semana"] == Decimal("70")
    assert p["veiculos"][0]["placa"] == "POU7015" and p["veiculos"][0]["locatario"] == "JOSE"
    assert p["veiculos"][0]["resultado"] == Decimal("75.00")
    assert len(p["grafico"]["colunas"]) == 6
    alertas = {a["titulo"]: a for a in p["alertas"]}
    assert alertas["Entradas do mês sem conta cadastrada"]["valor"] == Decimal("40.00")
    assert alertas["Despesas a repassar ao locatário"]["valor"] == Decimal("115")
    assert alertas["Motos em manutenção"]["valor"] == 1


def test_painel_seguro_devolve_o_painel_quando_tudo_funciona(monkeypatch):
    _preparar(monkeypatch)
    p = financeiro.painel_seguro(None, hoje=date(2026, 11, 4))
    assert "indisponivel" not in p and p["mes_texto"] == "2026-11" and p["atual"]["receita"] == Decimal("100.00")


def test_painel_seguro_nao_derruba_o_dashboard_se_a_leitura_falhar(monkeypatch, caplog):
    _preparar(monkeypatch)

    def falha(mes):
        raise RuntimeError("function rpc_detalhe_financeiro does not exist")

    monkeypatch.setattr(financeiro.repositorio, "detalhe_mensal", falha)

    with caplog.at_level("ERROR"):
        p = financeiro.painel_seguro("2026-08", hoje=date(2026, 11, 4))

    assert p["indisponivel"] is True
    assert p["mes_texto"] == "2026-08" and p["mes_anterior"] == "2026-07" and p["mes_seguinte"] == "2026-09"
    assert p["mes_rotulo"] == "agosto de 2026" and not p["e_mes_atual"] and p["mes_maximo"] == "2026-11"
    assert "atual" not in p
    assert "Não foi possível montar o painel financeiro" in caplog.text
