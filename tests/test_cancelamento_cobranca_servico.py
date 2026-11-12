"""Testes do serviço e do repositório de cancelamento de cobrança, com o Supabase falso."""

from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.repositories import cobrancas as repositorio
from src.services import cobrancas as servico

REPOSITORIO = "src.services.cobrancas.cobrancas"


def test_servico_cancela_pela_rpc():
    with patch(f"{REPOSITORIO}.cancelar_via_rpc", return_value={"status": "cancelada"}) as rpc:
        assert servico.cancelar_cobranca("c1", "Lançada por engano") == {"status": "cancelada"}
    rpc.assert_called_once_with("c1", "Lançada por engano")


def test_recusa_do_banco_vira_mensagem_para_a_tela():
    erro = APIError({"message": "Esta cobrança já tem pagamento registrado e não pode ser cancelada.", "code": "P0001"})
    with patch(f"{REPOSITORIO}.cancelar_via_rpc", side_effect=erro):
        with pytest.raises(ValueError, match="já tem pagamento registrado"):
            servico.cancelar_cobranca("c1", "Contestada")


def test_outros_erros_do_banco_nao_viram_mensagem():
    erro = APIError({"message": "Acesso negado.", "code": "42501"})
    with patch(f"{REPOSITORIO}.cancelar_via_rpc", side_effect=erro):
        with pytest.raises(APIError):
            servico.cancelar_cobranca("c1", "Contestada")


def test_repositorio_chama_a_rpc_com_os_parametros_certos():
    cliente = MagicMock()
    cliente.rpc.return_value.execute.return_value.data = {"cobranca_id": "c1", "status": "cancelada"}
    with patch("src.repositories.cobrancas.get_client", return_value=cliente):
        assert repositorio.cancelar_via_rpc("c1", "Motivo") == {"cobranca_id": "c1", "status": "cancelada"}
    cliente.rpc.assert_called_once_with("rpc_cancelar_cobranca", {"p_cobranca": "c1", "p_motivo": "Motivo"})
