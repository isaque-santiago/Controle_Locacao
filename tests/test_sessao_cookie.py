from unittest.mock import MagicMock, patch

from src import db


def test_le_tokens_dos_cookies_da_requisicao_sem_acionar_componente():
    contexto = MagicMock()
    contexto.cookies = {
        "sb_refresh_token": "refresh-valido",
        "sb_ultima_atividade": "1",
    }

    with patch.object(db.st, "context", contexto), patch(
        "src.db._get_cookie_controller"
    ) as controlador:
        assert db.get_refresh_token_cookie() == "refresh-valido"
        assert db.sessao_ativa_no_cookie() is True
        controlador.assert_not_called()


def test_cookie_ausente_na_requisicao_nao_consulta_componente_assincrono():
    contexto = MagicMock()
    contexto.cookies = {}

    with patch.object(db.st, "context", contexto), patch(
        "src.db._get_cookie_controller"
    ) as controlador:
        assert db.get_refresh_token_cookie() is None
        assert db.sessao_ativa_no_cookie() is False
        controlador.assert_not_called()


def test_usa_componente_em_versao_antiga_do_streamlit():
    controlador = MagicMock()
    controlador.get.side_effect = ["refresh-legado", "1"]

    with patch.object(db.st, "context", new=None), patch(
        "src.db._get_cookie_controller", return_value=controlador
    ):
        assert db.get_refresh_token_cookie() == "refresh-legado"
        assert db.sessao_ativa_no_cookie() is True


def test_limpeza_remove_cookies_sem_depender_de_leitura_assincrona():
    controlador = MagicMock()

    with patch.object(db.st, "session_state", {}), patch(
        "src.db._get_cookie_controller", return_value=controlador
    ):
        db.clear_session_tokens()

    controlador.remove.assert_any_call("sb_refresh_token")
    controlador.remove.assert_any_call("sb_ultima_atividade")
    controlador.get.assert_not_called()
