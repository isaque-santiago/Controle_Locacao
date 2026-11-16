"""Testes de src/domain/grupo_whatsapp.py (grupo do locatário e assuntos que vão a ele)."""

import pytest

from src.domain.avisos_whatsapp import TIPOS, Aviso
from src.domain.grupo_whatsapp import TIPOS_NO_GRUPO, eh_grupo, normalizar_grupo, somente_assuntos_do_grupo


@pytest.mark.parametrize("texto, esperado", [
    ("120363025246125486@g.us", "120363025246125486@g.us"),
    ("  120363025246125486@G.US ", "120363025246125486@g.us"),
    ("5511999998888-1600000000@g.us", "5511999998888-1600000000@g.us"),
    ("1203630252 46125486@g.us", "120363025246125486@g.us"),  # espaços de colagem
])
def test_aceita_ids_de_grupo(texto, esperado):
    assert normalizar_grupo(texto) == esperado


@pytest.mark.parametrize("texto", [None, "", "   ", "5511988887777", "5511988887777@s.whatsapp.net", "abc@g.us", "12345@g.us", "120363025246125486"])
def test_recusa_o_que_nao_e_grupo(texto):
    assert normalizar_grupo(texto) is None


def test_eh_grupo():
    assert eh_grupo("120363025246125486@g.us") and not eh_grupo("5511988887777") and not eh_grupo(None)


def test_so_cobrancas_e_recibos_vao_ao_grupo():
    assert TIPOS_NO_GRUPO == {"lembrete_vespera", "lembrete_vencimento", "atraso", "inadimplencia", "recibo_pagamento"}
    assert TIPOS_NO_GRUPO <= set(TIPOS)
    from datetime import date
    avisos = [Aviso(t, "c1", "r", date(2026, 11, 17), {}) for t in TIPOS]
    assert {a.tipo for a in somente_assuntos_do_grupo(avisos)} == TIPOS_NO_GRUPO
    assert somente_assuntos_do_grupo([]) == []
