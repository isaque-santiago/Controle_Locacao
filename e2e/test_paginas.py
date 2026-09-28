"""Fluxo 1 (Entrar e navegar por todas as páginas): linha de base de cada tela."""

import pytest

from e2e.ajudas import ir_para, tem_formulario_login
from e2e.config import PAGINAS
from e2e.verificacoes import capturar, verificar_layout, verificar_saude

pytestmark = pytest.mark.autenticado


def test_todas_as_paginas(pagina_logada, cenario, registrar, coletor, request):
    reg = registrar(cenario, fluxo="01-entrar-e-navegar")
    page = pagina_logada
    capturas = request.config.getoption("--capturas")

    for pagina in PAGINAS:
        try:
            ir_para(page, pagina)
        except Exception as erro:  # página que não carrega também é achado
            reg("P0", "pagina-nao-carrega", pagina.titulo, f"Falha ao abrir: {type(erro).__name__}")
            continue
        if tem_formulario_login(page):
            reg("P0", "sessao-perdida", pagina.titulo, "A navegação voltou para a tela de acesso.")
            continue
        verificar_layout(page, cenario, reg, pagina.titulo)
        verificar_saude(page, reg, pagina.titulo)
        if capturas:
            capturar(page, cenario, pagina.titulo)

    if request.config.getoption("--e2e-estrito"):
        p0 = [
            a
            for a in coletor.da_severidade("P0")
            if a.largura == cenario.largura and a.perfil == cenario.perfil and a.fluxo == "01-entrar-e-navegar"
        ]
        assert not p0, [f"{a.pagina}: {a.descricao}" for a in p0]
