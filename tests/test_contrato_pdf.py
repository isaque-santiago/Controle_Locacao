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


def test_varias_motos_saem_todas_no_pdf():
    outra = {"marca": "Yamaha", "modelo": "Factor 150", "placa": "QRS4T21", "cor": "Azul"}
    with patch.object(contrato_pdf, "get_locador", return_value={}):
        pdf = contrato_pdf.gerar(CONTRATO, CLIENTE, [MOTO, outra])
    assert pdf.startswith(b"%PDF-")

