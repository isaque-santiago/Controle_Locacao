"""Portal do locatário (Fase 7): serviço e telas, com o banco isolado por mocks."""

from decimal import Decimal
from pathlib import Path
from time import time
from unittest.mock import patch

import pytest
from postgrest.exceptions import APIError
from streamlit.testing.v1 import AppTest

from src.services import portal_locatario

RAIZ = Path(__file__).resolve().parents[1]
REPO = "src.services.portal_locatario.portal_locatario"

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
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


def _abrir(arquivo, papel, dados=DADOS):
    with (
        patch("src.services.portal_locatario.papel_atual", return_value=papel),
        patch("src.services.portal_locatario.dados_portal", return_value=dados),
    ):
        app = AppTest.from_file(str(RAIZ / arquivo), default_timeout=20)
        app.session_state["usuario"] = {"id": "u1", "email": "maria@example.com"}
        app.session_state["ultima_atividade"] = time()
        app.session_state["papel_usuario"] = papel
        return app.run()


class TestTelas:
    def test_portal_mostra_moto_formulario_e_multa(self):
        app = _abrir("pages/11_Portal_Locatario.py", "locatario")
        assert not app.exception and not app.error
        html = " ".join(m.value for m in app.markdown)
        assert "Olá, Maria" in html
        assert "ABC" in html
        assert any(t.label == "Hodômetro atual (km)" for t in app.text_input)
        avisos = " ".join(i.value for i in app.info)
        assert "R$ 50,00" in avisos
        assert "6.000 km" in avisos

    def test_portal_sem_contrato_ativo(self):
        app = _abrir("pages/11_Portal_Locatario.py", "locatario", {**DADOS, "contratos": []})
        assert not app.exception
        assert [i.value for i in app.info] == ["Você não tem contrato ativo no momento."]

    def test_envio_sem_fotos_e_recusado(self):
        app = _abrir("pages/11_Portal_Locatario.py", "locatario")
        app.text_input[0].set_value("6100")
        with (
            patch("src.services.portal_locatario.papel_atual", return_value="locatario"),
            patch("src.services.portal_locatario.dados_portal", return_value=DADOS),
            patch("src.services.portal_locatario.registrar_troca_oleo") as registrar,
        ):
            app.button[0].click().run()
        registrar.assert_not_called()
        assert [e.value for e in app.error] == ["Anexe a foto do painel e a foto da nota fiscal."]

    def test_usuario_sem_papel_nao_ve_nenhuma_tela(self):
        app = _abrir("app.py", None)
        assert not app.exception
        assert "não tem acesso ao sistema" in app.error[0].value
        assert not app.title  # nem o Dashboard do dono foi executado

    def test_locatario_no_app_ve_so_o_portal(self):
        app = _abrir("app.py", "locatario")
        assert not app.exception and not app.error
        assert "Olá, Maria" in " ".join(m.value for m in app.markdown)


class TestAlterarSenha:
    def test_portal_oferece_troca_de_senha_opcional_sem_bloquear_a_troca_de_oleo(self):
        app = _abrir("pages/11_Portal_Locatario.py", "locatario")
        assert not app.exception and not app.error
        assert [e.label for e in app.expander][-1] == "Alterar minha senha (opcional)"
        assert any(t.label == "Hodômetro atual (km)" for t in app.text_input)

    def test_trocar_senha_valida_e_chama_o_auth(self):
        with (
            patch(f"{REPO}.alterar_senha") as alterar,
            patch("src.services.portal_locatario.st.session_state", {"usuario": {"email": "52998224725@portal.example.com"}}),
        ):
            portal_locatario.trocar_senha("moto2026x", "moto2026x")
        alterar.assert_called_once_with("moto2026x")

    @pytest.mark.parametrize(
        "nova,confirmacao",
        [("moto2026x", "outra1234"), ("curta1", "curta1"), ("12345678", "12345678"), ("a52998224725", "a52998224725")],
    )
    def test_senha_fraca_ou_diferente_nao_chama_o_auth(self, nova, confirmacao):
        with (
            patch(f"{REPO}.alterar_senha") as alterar,
            patch("src.services.portal_locatario.st.session_state", {"usuario": {"email": "52998224725@portal.example.com"}}),
        ):
            with pytest.raises(ValueError):
                portal_locatario.trocar_senha(nova, confirmacao)
        alterar.assert_not_called()


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


class TestLoginPorCpf:
    def test_cpf_digitado_vira_email_interno_no_login(self):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=20).run()
        app.text_input[0].set_value("529.982.247-25")
        app.text_input[1].set_value("senha-qualquer")
        with patch("src.auth.login") as login:
            next(b for b in app.button if b.label == "Entrar no painel").click().run()
        login.assert_called_once_with("52998224725@portal.example.com", "senha-qualquer")


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
