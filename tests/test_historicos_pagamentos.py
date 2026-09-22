from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.repositories import pagamentos
from src.services import cobrancas


class _ConsultaPagamentos:
    def __init__(self, registros):
        self.registros = registros
        self.filtros_in = []

    def select(self, _selecao):
        return self

    def in_(self, campo, valores):
        self.filtros_in.append((campo, valores))
        return self

    def order(self, _campo):
        return self

    def range(self, _inicio, _fim):
        return self

    def execute(self):
        return SimpleNamespace(data=self.registros)


def test_repositorio_carrega_varias_cobrancas_em_uma_consulta():
    consulta = _ConsultaPagamentos(
        [{"id": "p1", "cobranca_id": "c1", "data_pagamento": "2026-09-01"}]
    )
    cliente = Mock()
    cliente.table.return_value = consulta

    with patch("src.repositories.pagamentos.get_client", return_value=cliente):
        resultado = pagamentos.listar_por_cobrancas(["c1", "c2", "c1"])

    assert resultado == consulta.registros
    assert consulta.filtros_in == [("cobranca_id", ["c1", "c2"])]
    cliente.table.assert_called_once_with("pagamentos")


def test_servico_agrupa_historicos_com_uma_chamada_ao_repositorio():
    registros = [
        {"id": "p1", "cobranca_id": "c1"},
        {"id": "p2", "cobranca_id": "c1"},
        {"id": "p3", "cobranca_id": "c2"},
    ]
    with patch(
        "src.services.cobrancas.pagamentos.listar_por_cobrancas",
        return_value=registros,
    ) as listar:
        resultado = cobrancas.historicos_pagamentos(["c1", "c2"])

    listar.assert_called_once_with(["c1", "c2"])
    assert resultado == {"c1": registros[:2], "c2": registros[2:]}
