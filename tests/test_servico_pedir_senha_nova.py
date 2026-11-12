"""ServicoAutenticacao.pedir_senha_nova: chama a RPC pública com o cliente anônimo (sem login)."""

from unittest.mock import MagicMock, patch

from src.services.autenticacao import ServicoAutenticacao


def test_pede_pela_rpc_com_o_cliente_anonimo():
    cliente = MagicMock()
    with patch("src.services.autenticacao.db.criar_cliente_anonimo", return_value=cliente) as anonimo:
        ServicoAutenticacao().pedir_senha_nova("52998224725")
    anonimo.assert_called_once_with()
    cliente.rpc.assert_called_once_with("rpc_portal_pedir_redefinicao", {"p_cpf": "52998224725"})
    cliente.rpc.return_value.execute.assert_called_once_with()
