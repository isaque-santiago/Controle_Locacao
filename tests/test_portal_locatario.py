"""Portal do locatário (Fase 7): serviço e repositório, com o banco isolado por mocks."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.services import portal_locatario

REPO = "src.services.portal_locatario.portal_locatario"

def _png_valido() -> bytes:
    import io

    from PIL import Image

    saida = io.BytesIO()
    Image.new("RGB", (4, 4), (9, 9, 9)).save(saida, "PNG")
    return saida.getvalue()


PNG = _png_valido()
CONTRATO = {
    "contrato_id": "ct1",
    "placa": "ABC1D23",
    "modelo": "CG 160",
    "km_atual": 5900,
    "ultima_km": 5000,
    "ultima_data": "2026-09-01",
    "intervalo_km": 1000,
    "intervalo_dias": 90,
    "trocas": [],
}
DADOS = {
    "cliente_id": "cli1",
    "nome": "Maria Souza",
    "multa_valor": 50,
    "alerta_km": 300,
    "alerta_dias": 15,
    "contratos": [CONTRATO],
}


def _registrar(km="6100", foto=("painel.png", PNG), nota=("nota.png", PNG)):
    return portal_locatario.registrar_troca_oleo(
        "cli1", CONTRATO, km, foto, nota, Decimal("50.00")
    )


class TestRegistrarTrocaOleo:
    def test_envia_as_duas_fotos_e_chama_a_rpc(self):
        with (
            patch(f"{REPO}.enviar_arquivo", side_effect=["cli1/a.png", "cli1/b.png"]) as enviar,
            patch(f"{REPO}.registrar_troca", return_value={"excedeu": True}) as rpc,
        ):
            resultado = _registrar()
        assert resultado == {"excedeu": True}
        assert enviar.call_count == 2
        assert rpc.call_args.args[0] == {
            "contrato_id": "ct1",
            "km": 6100,
            "foto_painel_path": "cli1/a.png",
            "nota_fiscal_path": "cli1/b.png",
        }

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"km": "5899"},  # km regrediu
            {"km": "abc"},
            {"foto": ("painel.gif", PNG)},  # extensão fora da lista
            {"nota": ("nota.png", b"nao e png")},  # assinatura não confere
            {"foto": ("painel.png", b"")},
        ],
    )
    def test_erro_previsivel_nao_envia_nada(self, kwargs):
        with patch(f"{REPO}.enviar_arquivo") as enviar, patch(f"{REPO}.registrar_troca") as rpc:
            with pytest.raises(ValueError):
                _registrar(**kwargs)
        enviar.assert_not_called()
        rpc.assert_not_called()

    def test_mensagem_da_rpc_vira_erro_de_regra(self):
        erro = APIError(
            {"message": "Contrato ativo não encontrado para este acesso.", "code": "P0001"}
        )
        with (
            patch(f"{REPO}.enviar_arquivo", return_value="cli1/a.png"),
            patch(f"{REPO}.registrar_troca", side_effect=erro),
        ):
            with pytest.raises(ValueError, match="Contrato ativo não encontrado"):
                _registrar()

    def test_erro_de_permissao_nao_e_escondido(self):
        erro = APIError({"message": "Acesso negado.", "code": "42501"})
        with (
            patch(f"{REPO}.enviar_arquivo", return_value="cli1/a.png"),
            patch(f"{REPO}.registrar_troca", side_effect=erro),
        ):
            with pytest.raises(APIError):
                _registrar()


class TestAcessoDoLocatario:
    def test_criar_devolve_email_e_senha_da_funcao(self):
        resposta = {"ok": True, "email": "52998224725@portal.example.com", "senha": "Abc23def45"}
        with patch(f"{REPO}.gerenciar_acesso", return_value=resposta) as funcao:
            assert portal_locatario.criar_acesso("cli1") == {
                "email": "52998224725@portal.example.com",
                "senha": "Abc23def45",
            }
        funcao.assert_called_once_with("criar", "cli1")

    def test_redefinir_e_remover_chamam_a_acao_certa(self):
        with patch(f"{REPO}.gerenciar_acesso", return_value={"ok": True, "email": "e", "senha": "s"}) as funcao:
            portal_locatario.redefinir_senha("cli1")
            portal_locatario.remover_acesso("cli1")
        assert [c.args for c in funcao.call_args_list] == [("redefinir", "cli1"), ("remover", "cli1")]

    @pytest.mark.parametrize(
        "resposta,mensagem",
        [
            ({"ok": False, "erro": "Este cliente já tem acesso."}, "já tem acesso"),
            ({"ok": False}, "Não foi possível concluir"),
            (None, "Não foi possível concluir"),
            (b"<html>", "Não foi possível concluir"),
        ],
    )
    def test_erro_da_funcao_vira_mensagem_para_o_dono(self, resposta, mensagem):
        with patch(f"{REPO}.gerenciar_acesso", return_value=resposta):
            with pytest.raises(ValueError, match=mensagem):
                portal_locatario.criar_acesso("cli1")


class TestRepositorioAcesso:
    def test_chama_a_edge_function_com_o_jwt_do_dono(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from src.repositories import portal_locatario as repositorio

        cliente = MagicMock()
        cliente.auth.get_session.return_value = SimpleNamespace(access_token="jwt-do-dono")
        cliente.functions.invoke.return_value = {"ok": True}
        with patch.object(repositorio, "get_client", return_value=cliente):
            assert repositorio.gerenciar_acesso("criar", "cli1") == {"ok": True}
        (nome,) = cliente.functions.invoke.call_args.args
        opcoes = cliente.functions.invoke.call_args.kwargs["invoke_options"]
        assert nome == "criar-locatario"
        assert opcoes["headers"] == {"Authorization": "Bearer jwt-do-dono"}
        assert opcoes["body"] == {"acao": "criar", "cliente_id": "cli1"}
        assert opcoes["responseType"] == "json"

    def test_no_app_web_usa_o_jwt_do_cabecalho_do_cliente(self):
        from unittest.mock import MagicMock

        from src.repositories import portal_locatario as repositorio

        cliente = MagicMock()
        cliente.auth.get_session.return_value = None
        cliente.options.headers = {"Authorization": "Bearer jwt-da-requisicao"}
        cliente.functions.invoke.return_value = {"ok": True}
        with patch.object(repositorio, "get_client", return_value=cliente):
            repositorio.gerenciar_acesso("criar", "cli1")
        opcoes = cliente.functions.invoke.call_args.kwargs["invoke_options"]
        assert opcoes["headers"] == {"Authorization": "Bearer jwt-da-requisicao"}
