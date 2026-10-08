"""Leitura do cadastro de documento e validação do comprovante."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain import formulario_documento as f
from src.domain.formulario_moto import ErroDeCampos

HOJE = date(2026, 10, 8)
MOTOS = {"m1", "m2"}


def _entrada(**extra):
    return {"moto_id": "m1", "tipo": "ipva", "ano_referencia": "2026", "vencimento": "2026-12-31", "valor": "1.234,56",
            "descricao": " apólice 22 ", "observacoes": "", **extra}


def test_inicial_e_com_sugestao():
    v = f.documento_inicial(HOJE)
    assert v["tipo"] == "ipva" and v["ano_referencia"] == "2026" and v["vencimento"] == "" and v["valor"] == "0,00"
    s = f.documento_inicial(HOJE, "m2", "seguro", 2027)
    assert (s["moto_id"], s["tipo"], s["ano_referencia"], s["vencimento"]) == ("m2", "seguro", "2027", "")
    assert f.documento_inicial(HOJE, tipo="invalido")["tipo"] == "ipva"


def test_valores_do_documento_existente():
    v = f.valores_do_documento({"moto_id": "m1", "tipo": "seguro", "ano_referencia": 2026, "vencimento": "2026-12-31T00:00:00",
                                "valor": Decimal("150"), "descricao": None, "observacoes": "obs"})
    assert v["vencimento"] == "2026-12-31" and v["valor"] == "150,00" and v["descricao"] == "" and v["observacoes"] == "obs"


def test_le_documento_valido():
    dados = f.ler_documento(_entrada(), MOTOS)
    assert dados == {"moto_id": "m1", "tipo": "ipva", "ano_referencia": 2026, "vencimento": "2026-12-31",
                     "descricao": "apólice 22", "valor": "1234.56", "observacoes": None}
    assert f.ler_documento(_entrada(moto_id="x"), MOTOS, moto_fixa="m2")["moto_id"] == "m2"  # edição: a moto não muda


@pytest.mark.parametrize("extra,campo", [
    ({"moto_id": "x"}, "moto_id"), ({"tipo": "x"}, "tipo"), ({"ano_referencia": "1899"}, "ano_referencia"),
    ({"ano_referencia": "2101"}, "ano_referencia"), ({"ano_referencia": "abc"}, "ano_referencia"),
    ({"vencimento": ""}, "vencimento"), ({"vencimento": "31/12/2026"}, "vencimento"),
    ({"valor": ""}, "valor"), ({"valor": "-5"}, "valor"), ({"valor": "1,234"}, "valor"),
])
def test_valida_campo_a_campo(extra, campo):
    with pytest.raises(ErroDeCampos) as erro:
        f.ler_documento(_entrada(**extra), MOTOS)
    assert campo in erro.value.erros


def test_moto_fixa_invalida_e_varios_erros_juntos():
    with pytest.raises(ErroDeCampos) as erro:
        f.ler_documento(_entrada(tipo="x", valor=""), MOTOS, moto_fixa="fora")
    assert set(erro.value.erros) == {"moto_id", "tipo", "valor"}


PDF = b"%PDF-1.7" + b"0" * 8


def test_comprovante_valido():
    f.validar_comprovante("a.pdf", 100, PDF)
    f.validar_comprovante("a.JPG", 100, b"\xff\xd8\xff" + b"0" * 13)


@pytest.mark.parametrize("nome,tamanho,cabecalho,trecho", [
    ("a.pdf", 11 * 1024 * 1024, PDF, "mais de 10 MB"),
    ("a.exe", 10, b"MZ", "Extensão não permitida"),
    ("a.pdf", 10, b"nada", "não corresponde"),
    ("a.pdf", 0, b"", "vazio"),
])
def test_comprovante_invalido(nome, tamanho, cabecalho, trecho):
    with pytest.raises(ErroDeCampos) as erro:
        f.validar_comprovante(nome, tamanho, cabecalho)
    assert trecho in erro.value.erros["comprovante"]
