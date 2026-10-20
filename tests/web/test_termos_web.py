"""Página de Termos e privacidade e o atalho no menu da conta."""

from tests.web.conftest import entrar


def test_pagina_de_termos_abre_para_o_dono_logado(cliente):
    entrar(cliente)
    html = cliente.get("/termos").text
    assert "Termos e privacidade" in html and "Direitos dos titulares (LGPD)" in html


def test_menu_da_conta_leva_aos_termos(cliente):
    entrar(cliente)
    assert 'href="/termos"' in cliente.get("/").text


def test_termos_exigem_login(cliente):
    resposta = cliente.get("/termos", follow_redirects=False)
    assert resposta.status_code in (303, 401)
