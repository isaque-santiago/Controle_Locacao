"""Contrato com várias motos: vistoria de entrega e de devolução de cada moto vinculada (serviço)."""

from datetime import date
from unittest.mock import patch

import pytest

from src.services import contratos

DADOS = {
    "moto_id": "m1", "cliente_id": "c", "data_inicio": "2026-10-23", "periodicidade": "semanal",
    "valor_periodo": "350.00", "caucao_valor": "500.00", "km_inicial": 100, "motos_vinculadas": ["m2"],
}
VISTORIA = {"km": 100}
MOTOS = [{"id": "m1", "km_atual": 100}, {"id": "m2", "km_atual": 500}]
MOTOS_DO_CONTRATO = [{"moto_id": "m1", "principal": True}, {"moto_id": "m2", "principal": False}]


@pytest.fixture(autouse=True)
def km_das_motos():
    with patch("src.services.contratos.repo_motos.listar", return_value=MOTOS):
        yield


class TestCriar:
    def test_envia_as_vistorias_das_vinculadas_validadas(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
            contratos.criar_com_vistoria(DADOS, VISTORIA, [{"moto_id": " m2 ", "km": "520", "checklist": {}}])
        assert rpc.call_args.args[2] == [{"moto_id": "m2", "km": 520, "checklist": {}}]

    def test_sem_vistorias_das_vinculadas_chama_como_antes(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
            contratos.criar_com_vistoria(DADOS, VISTORIA)
        assert len(rpc.call_args.args) == 2

    def test_exigir_todas_recusa_quando_falta_uma_vinculada(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="todas as motos"):
                contratos.criar_com_vistoria(DADOS, VISTORIA, [], exigir_todas=True)
        rpc.assert_not_called()

    def test_exigir_todas_aceita_quando_todas_tem_vistoria(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
            contratos.criar_com_vistoria(DADOS, VISTORIA, [{"moto_id": "m2", "km": 500}], exigir_todas=True)
        rpc.assert_called_once()

    def test_exigir_todas_nao_atrapalha_contrato_de_uma_moto(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
            contratos.criar_com_vistoria({**DADOS, "motos_vinculadas": []}, VISTORIA, None, exigir_todas=True)
        rpc.assert_called_once()

    def test_recusa_km_da_vinculada_menor_que_o_atual(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="menor que a atual"):
                contratos.criar_com_vistoria(DADOS, VISTORIA, [{"moto_id": "m2", "km": 10}])
        rpc.assert_not_called()

    def test_recusa_vistoria_de_moto_de_fora_do_contrato(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="não pertence"):
                contratos.criar_com_vistoria(DADOS, VISTORIA, [{"moto_id": "m9", "km": 10}])
        rpc.assert_not_called()


class TestEncerrar:
    def _encerrar(self, vinculadas, **extra):
        with patch("src.services.contratos.contratos.listar_motos_do_contrato", return_value=MOTOS_DO_CONTRATO), \
             patch("src.services.contratos.contratos.encerrar_com_vistoria", return_value={}) as rpc:
            contratos.encerrar_com_vistoria("ct", date(2026, 11, 5), {"km": 150}, vistorias_vinculadas=vinculadas, **extra)
        return rpc

    def test_envia_a_devolucao_das_vinculadas_validadas(self):
        rpc = self._encerrar([{"moto_id": "m2", "km": "560"}])
        assert rpc.call_args.args[5] == [{"moto_id": "m2", "km": 560}]

    def test_sem_vistorias_das_vinculadas_chama_como_antes(self):
        with patch("src.services.contratos.contratos.encerrar_com_vistoria", return_value={}) as rpc, \
             patch("src.services.contratos.contratos.listar_motos_do_contrato") as leitura:
            contratos.encerrar_com_vistoria("ct", date(2026, 11, 5), {"km": 150})
        assert len(rpc.call_args.args) == 5
        leitura.assert_not_called()

    def test_exigir_todas_recusa_quando_falta_devolucao_de_vinculada(self):
        with patch("src.services.contratos.contratos.listar_motos_do_contrato", return_value=MOTOS_DO_CONTRATO), \
             patch("src.services.contratos.contratos.encerrar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="todas as motos"):
                contratos.encerrar_com_vistoria("ct", date(2026, 11, 5), {"km": 150}, exigir_todas=True)
        rpc.assert_not_called()

    def test_recusa_km_da_vinculada_menor_que_o_atual(self):
        with patch("src.services.contratos.contratos.listar_motos_do_contrato", return_value=MOTOS_DO_CONTRATO), \
             patch("src.services.contratos.contratos.encerrar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="menor que a atual"):
                contratos.encerrar_com_vistoria(
                    "ct", date(2026, 11, 5), {"km": 150}, vistorias_vinculadas=[{"moto_id": "m2", "km": 1}])
        rpc.assert_not_called()

    def test_contrato_inexistente(self):
        with patch("src.services.contratos.contratos.listar_motos_do_contrato", return_value=[]):
            with pytest.raises(ValueError, match="não encontrado"):
                contratos.encerrar_com_vistoria("ct", date(2026, 11, 5), {"km": 150}, exigir_todas=True)


def test_repositorio_so_manda_o_parametro_novo_quando_ha_vistorias_das_vinculadas():
    from unittest.mock import MagicMock

    from src.repositories import contratos as repositorio

    cliente = MagicMock()
    with patch.object(repositorio, "get_client", return_value=cliente), patch.object(repositorio, "invalida_cache", create=True):
        repositorio.criar_com_vistoria({"moto_id": "m1"}, {"km": 1})
        sem = cliente.rpc.call_args.args[1]
        repositorio.criar_com_vistoria({"moto_id": "m1"}, {"km": 1}, [{"moto_id": "m2", "km": 2}])
        com = cliente.rpc.call_args.args[1]
    assert "p_vistorias_vinculadas" not in sem
    assert com["p_vistorias_vinculadas"] == [{"moto_id": "m2", "km": 2}]
