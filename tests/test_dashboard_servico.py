"""Serviço do Dashboard: o mês corrente e o mesmo intervalo do mês anterior saem de uma única leitura dos dados."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.services import dashboard


def test_resumo_traz_recebido_e_manutencao_do_mes_anterior(monkeypatch):
    pedidos = []

    def periodos(lista):
        pedidos.append(lista)
        atual = {"resultado": [{"receita_recebida": Decimal("1000"), "custo_manutencao": Decimal("50")}]}
        anterior = {"resultado": [{"receita_recebida": Decimal("800"), "custo_manutencao": Decimal("90")},
                                  {"receita_recebida": Decimal("100"), "custo_manutencao": Decimal("10")}]}
        return [atual, anterior]

    monkeypatch.setattr(dashboard, "hoje_br", lambda: date(2026, 10, 23))
    monkeypatch.setattr(dashboard, "relatorios", SimpleNamespace(resultados_por_periodos=periodos))
    monkeypatch.setattr(dashboard, "motos", SimpleNamespace(listar=lambda: []))
    monkeypatch.setattr(dashboard, "cobrancas", SimpleNamespace(listar=lambda: []))
    monkeypatch.setattr(dashboard, "clientes", SimpleNamespace(listar=lambda: []))

    dados = dashboard.resumo()

    assert pedidos == [[(date(2026, 10, 1), date(2026, 10, 23)), (date(2026, 9, 1), date(2026, 9, 23))]]
    assert dados["recebido"] == Decimal("1000") and dados["manutencao"] == Decimal("50")
    assert dados["recebido_anterior"] == Decimal("900") and dados["manutencao_anterior"] == Decimal("100")
