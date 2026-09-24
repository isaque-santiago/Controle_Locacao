"""Testes de src/services/contrato_pdf.py (dados fictícios)."""

import re
from decimal import Decimal
from unittest.mock import patch

from src.services import contrato_pdf

CONTRATO = {
    "data_inicio": "2026-03-05",
    "data_fim_prevista": "2026-09-05",
    "periodicidade": "semanal",
    "valor_periodo": Decimal("250.00"),
    "caucao_valor": Decimal("400.00"),
    "km_inicial": 12500,
}
CLIENTE = {"nome": "Fulano de Tal", "cpf": "52998224725", "email": "f@exemplo.com"}
MOTO = {"marca": "Honda", "modelo": "CG 160", "placa": "ABC1D23", "cor": "Preta"}


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_gera_pdf_valido_com_varias_paginas():
    with patch.object(contrato_pdf, "get_locador", return_value={"nome": "Empresa Exemplo"}):
        pdf = contrato_pdf.gerar(CONTRATO, CLIENTE, MOTO)
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert _paginas(pdf) >= 6


def test_gera_mesmo_sem_dados_do_locador():
    with patch.object(contrato_pdf, "get_locador", return_value={}):
        assert contrato_pdf.gerar(CONTRATO, CLIENTE, MOTO).startswith(b"%PDF-")


def test_nome_fora_do_latin1_nao_quebra_a_geracao():
    cliente = {**CLIENTE, "nome": "Zażółć Gęślą"}
    with patch.object(contrato_pdf, "get_locador", return_value={}):
        assert contrato_pdf.gerar(CONTRATO, cliente, MOTO).startswith(b"%PDF-")


def test_ficha_oferece_o_pdf_sem_gerar_a_cada_recarga():
    from streamlit.testing.v1 import AppTest

    def script():
        from src.ui import contratos
        from tests.test_contrato_pdf import CLIENTE, CONTRATO, MOTO

        contratos._cabecalho_ficha(
            {**CONTRATO, "status": "ativo", "id": "c1"},
            {**MOTO, "id": "m1"},
            {**CLIENTE, "id": "cl1"},
        )

    with patch("src.services.contrato_pdf.gerar") as gerar:
        app = AppTest.from_function(script, default_timeout=20).run()
    assert not app.exception
    botoes = app.get("download_button")
    assert len(botoes) == 1
    assert botoes[0].proto.label == "Contrato em PDF"
    gerar.assert_not_called()  # o PDF só é montado no clique, não a cada rerun
