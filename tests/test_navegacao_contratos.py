from unittest.mock import patch

from src.ui import componentes


def test_abrir_ficha_contrato_seleciona_contrato_e_aba():
    estado = {}
    with (
        patch.object(componentes.st, "session_state", estado),
        patch.object(componentes.st, "switch_page") as trocar,
    ):
        componentes.abrir_ficha_contrato("contrato-1")

    assert estado == {
        "ficha_contrato": "contrato-1",
        "contratos_aba_inicial": "Ficha e encerramento",
    }
    trocar.assert_called_once_with("pages/4_Contratos.py")
