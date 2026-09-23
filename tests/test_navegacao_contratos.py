from unittest.mock import patch

from src.ui import componentes


def test_abrir_ficha_contrato_seleciona_contrato_na_ficha():
    estado = {}
    with (
        patch.object(componentes.st, "session_state", estado),
        patch.object(componentes.st, "switch_page") as trocar,
    ):
        componentes.abrir_ficha_contrato("contrato-1")

    assert estado == {
        "contratos_visao": "ficha",
        "contratos_id_selecionado": "contrato-1",
    }
    trocar.assert_called_once_with("pages/4_Contratos.py")
