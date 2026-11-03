"""Contrato com mais de uma moto: regra pura e serviço (a moto principal concentra parcela e receita)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.domain.contrato_motos import MAX_MOTOS_POR_CONTRATO, normalizar_motos_vinculadas, todas_as_motos
from src.services import contratos

DADOS = {
    "moto_id": "m1",
    "cliente_id": "c",
    "data_inicio": "2026-10-23",
    "periodicidade": "semanal",
    "valor_periodo": "350.00",
    "caucao_valor": "500.00",
    "km_inicial": 100,
}
VISTORIA = {"km": 100}


class TestNormalizar:
    def test_sem_vinculadas_devolve_lista_vazia(self):
        assert normalizar_motos_vinculadas("m1", None) == []
        assert normalizar_motos_vinculadas("m1", []) == []

    def test_ignora_vazios_e_espacos(self):
        assert normalizar_motos_vinculadas("m1", [" m2 ", "", None]) == ["m2"]

    def test_recusa_repeticao(self):
        with pytest.raises(ValueError, match="mais de uma vez"):
            normalizar_motos_vinculadas("m1", ["m2", "m2"])

    def test_recusa_a_principal_na_lista(self):
        with pytest.raises(ValueError, match="principal"):
            normalizar_motos_vinculadas("m1", ["m1"])

    def test_limite_de_motos_conta_a_principal(self):
        ok = [f"v{i}" for i in range(MAX_MOTOS_POR_CONTRATO - 1)]
        assert normalizar_motos_vinculadas("m1", ok) == ok
        with pytest.raises(ValueError, match=str(MAX_MOTOS_POR_CONTRATO)):
            normalizar_motos_vinculadas("m1", ok + ["extra"])

    def test_todas_as_motos_a_principal_vem_primeiro(self):
        assert todas_as_motos("m1", ["m2", "m3"]) == ["m1", "m2", "m3"]


class TestServico:
    def test_criar_contrato_envia_as_vinculadas(self):
        with patch("src.services.contratos.contratos.criar_via_rpc", return_value={}) as rpc:
            contratos.criar_contrato("m1", "c", date(2026, 10, 23), "semanal", Decimal("350.00"), motos_vinculadas=["m2"])
        assert rpc.call_args.args[0]["motos_vinculadas"] == ["m2"]
        assert rpc.call_args.args[0]["moto_id"] == "m1"

    def test_criar_contrato_sem_vinculadas_nao_envia_a_chave(self):
        with patch("src.services.contratos.contratos.criar_via_rpc", return_value={}) as rpc:
            contratos.criar_contrato("m1", "c", date(2026, 10, 23), "semanal", Decimal("350.00"))
        assert "motos_vinculadas" not in rpc.call_args.args[0]

    def test_criar_contrato_recusa_vinculada_igual_a_principal(self):
        with patch("src.services.contratos.contratos.criar_via_rpc") as rpc:
            with pytest.raises(ValueError, match="principal"):
                contratos.criar_contrato("m1", "c", date(2026, 10, 23), "semanal", Decimal("350.00"), motos_vinculadas=["m1"])
        rpc.assert_not_called()

    def test_criar_com_vistoria_valida_e_normaliza_as_vinculadas(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
            contratos.criar_com_vistoria({**DADOS, "motos_vinculadas": [" m2 "]}, VISTORIA)
        assert rpc.call_args.args[0]["motos_vinculadas"] == ["m2"]

    def test_criar_com_vistoria_recusa_repeticao(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="mais de uma vez"):
                contratos.criar_com_vistoria({**DADOS, "motos_vinculadas": ["m2", "m2"]}, VISTORIA)
        rpc.assert_not_called()

    def test_motos_do_contrato_le_a_view(self):
        linhas = [{"moto_id": "m1", "principal": True, "placa": "POP9E24"}]
        with patch("src.services.contratos.contratos.listar_motos_do_contrato", return_value=linhas) as leitura:
            assert contratos.motos_do_contrato("ct") == linhas
        leitura.assert_called_once_with("ct")
