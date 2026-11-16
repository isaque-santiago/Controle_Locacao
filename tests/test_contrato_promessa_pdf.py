"""PDF do contrato com promessa de compra e venda (src/services/contrato_promessa_pdf.py) e a escolha do modelo."""

from unittest.mock import patch

from src.services import contrato_pdf, contrato_promessa_pdf
from tests.test_contrato_promessa import CLIENTE, CONTRATO, LOCADOR, MOTO


def _paginas(pdf: bytes) -> int:
    return pdf.count(b"/Type /Page\n") or pdf.count(b"/Type /Page ") or pdf.count(b"/Type/Page")


def test_gera_um_pdf_de_varias_paginas():
    with patch.object(contrato_pdf, "get_locador", return_value=LOCADOR):
        pdf = contrato_pdf.gerar(CONTRATO, CLIENTE, MOTO)
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000
    assert _paginas(pdf) >= 6


def test_sem_logo_nem_marca_dagua_o_pdf_sai_igual(tmp_path):
    with patch.object(contrato_promessa_pdf, "PASTA_IMAGENS", tmp_path), patch.object(contrato_pdf, "get_locador", return_value=LOCADOR):
        pdf = contrato_pdf.gerar(CONTRATO, CLIENTE, MOTO)
    assert pdf.startswith(b"%PDF")


def test_varias_motos_e_dados_em_branco_nao_quebram_o_pdf():
    vazio = {k: None for k in CLIENTE if k not in ("nome", "cpf")}
    with patch.object(contrato_pdf, "get_locador", return_value={}):
        pdf = contrato_pdf.gerar(CONTRATO, {**vazio, "nome": "Zé Ñandú Ωmega", "cpf": "52998224725"}, [MOTO, {**MOTO, "placa": "BRA2E19"}])
    assert pdf.startswith(b"%PDF")


def test_promessa_de_compra_usa_o_modelo_novo_e_locacao_o_antigo():
    with patch.object(contrato_pdf, "get_locador", return_value=LOCADOR), \
            patch.object(contrato_pdf.contrato_promessa_pdf, "renderizar", return_value=b"novo") as novo, \
            patch.object(contrato_pdf, "renderizar", return_value=b"antigo") as antigo:
        assert contrato_pdf.gerar({**CONTRATO, "tipo_contrato": "promessa_compra"}, CLIENTE, MOTO) == b"novo"
        assert contrato_pdf.gerar({**CONTRATO, "tipo_contrato": "locacao"}, CLIENTE, MOTO) == b"antigo"
    blocos, cabecalho, rodape = novo.call_args.args
    assert blocos[0].tipo == "titulo" and cabecalho["contato"] == "Crato/CE · (88) 9 9806-4387"
    assert rodape == "Contrato de Locação com Promessa de Compra e Venda - Alberto Filho da Silva Costa"
    assert antigo.call_count == 1


def test_contrato_sem_tipo_continua_no_modelo_antigo():
    with patch.object(contrato_pdf, "get_locador", return_value=LOCADOR), patch.object(contrato_pdf, "renderizar", return_value=b"antigo"):
        dados = {k: v for k, v in CONTRATO.items() if k != "tipo_contrato"}
        assert contrato_pdf.gerar(dados, CLIENTE, MOTO) == b"antigo"
