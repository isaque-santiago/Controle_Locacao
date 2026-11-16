"""PDF dos contratos com e sem promessa de compra (src/services/contrato_la_pdf.py e contrato_pdf.py)."""

from unittest.mock import patch

from src.services import contrato_pdf, contrato_la_pdf
from tests.test_contrato_la import CLIENTE, CONTRATO, LOCADOR, MOTO


def _paginas(pdf: bytes) -> int:
    return pdf.count(b"/Type /Page\n") or pdf.count(b"/Type /Page ") or pdf.count(b"/Type/Page")


def test_gera_um_pdf_de_varias_paginas():
    with patch.object(contrato_pdf, "get_locador", return_value=LOCADOR):
        pdf = contrato_pdf.gerar(CONTRATO, CLIENTE, MOTO)
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000
    assert _paginas(pdf) >= 6


def test_sem_logo_nem_marca_dagua_o_pdf_sai_igual(tmp_path):
    with patch.object(contrato_la_pdf, "PASTA_IMAGENS", tmp_path), patch.object(contrato_pdf, "get_locador", return_value=LOCADOR):
        pdf = contrato_pdf.gerar(CONTRATO, CLIENTE, MOTO)
    assert pdf.startswith(b"%PDF")


def test_varias_motos_e_dados_em_branco_nao_quebram_o_pdf():
    vazio = {k: None for k in CLIENTE if k not in ("nome", "cpf")}
    with patch.object(contrato_pdf, "get_locador", return_value={}):
        pdf = contrato_pdf.gerar(CONTRATO, {**vazio, "nome": "Zé Ñandú Ωmega", "cpf": "52998224725"}, [MOTO, {**MOTO, "placa": "BRA2E19"}])
    assert pdf.startswith(b"%PDF")


def test_promessa_e_locacao_usam_o_mesmo_visual_com_subtitulo_e_rodape_proprios():
    with patch.object(contrato_pdf, "get_locador", return_value=LOCADOR), \
            patch.object(contrato_pdf.contrato_la_pdf, "renderizar", return_value=b"pdf") as desenhar:
        contrato_pdf.gerar({**CONTRATO, "tipo_contrato": "promessa_compra"}, CLIENTE, MOTO)
        contrato_pdf.gerar({**CONTRATO, "tipo_contrato": "locacao"}, CLIENTE, MOTO)
    (blocos_p, cab_p, rodape_p), (blocos_l, cab_l, rodape_l) = (c.args for c in desenhar.call_args_list)
    assert "PROMESSA DE COMPRA E VENDA" in blocos_p[0].texto and "PROMESSA" not in blocos_l[0].texto
    assert cab_p["subtitulo"] == "Locação de motocicletas com promessa de compra e venda" and cab_l["subtitulo"] == "Locação de motocicletas"
    assert cab_p["contato"] == cab_l["contato"] == "Crato/CE · (88) 9 9806-4387"
    assert rodape_p == "Contrato de Locação com Promessa de Compra e Venda - Alberto Filho da Silva Costa"
    assert rodape_l == "Contrato de Locação de Veículo - Alberto Filho da Silva Costa"


def test_locacao_simples_gera_um_pdf_no_mesmo_template():
    contrato = {**CONTRATO, "tipo_contrato": "locacao", "numero_parcelas": None, "valor_total": None}
    with patch.object(contrato_pdf, "get_locador", return_value=LOCADOR):
        pdf = contrato_pdf.gerar(contrato, CLIENTE, MOTO)
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000
    assert _paginas(pdf) >= 6
