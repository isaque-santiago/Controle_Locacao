"""Fluxo 1 (Entrar e navegar por todas as páginas): linha de base de cada tela."""

import pytest

from e2e.ajudas import ir_para, tem_formulario_login
from e2e.config import PAGINAS
from e2e.verificacoes import (
    achados_bloqueantes,
    capturar,
    verificar_acessibilidade,
    verificar_layout,
    verificar_saude,
    verificar_teclado,
)

pytestmark = pytest.mark.autenticado


def test_todas_as_paginas(pagina_logada, cenario, registrar, coletor, request):
    reg = registrar(cenario, fluxo="01-entrar-e-navegar")
    page = pagina_logada
    capturas = request.config.getoption("--capturas")

    for pagina in PAGINAS:
        try:
            reautenticou = ir_para(page, pagina)
        except Exception as erro:  # página que não carrega também é achado
            reg("P0", "pagina-nao-carrega", pagina.titulo, f"Falha ao abrir: {type(erro).__name__}")
            continue
        if reautenticou:
            reg(
                "P2",
                "sessao-restaurada-por-novo-login",
                pagina.titulo,
                "A sessão não sobreviveu à navegação por URL; foi preciso entrar de novo.",
            )
        if tem_formulario_login(page):
            reg("P0", "sessao-perdida", pagina.titulo, "A navegação voltou para a tela de acesso.")
            continue
        verificar_layout(page, cenario, reg, pagina.titulo)
        verificar_saude(page, reg, pagina.titulo)
        verificar_acessibilidade(page, reg, pagina.titulo)
        verificar_teclado(page, reg, pagina.titulo)
        if capturas:
            capturar(page, cenario, pagina.titulo)

    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, fluxo="01-entrar-e-navegar")
        assert not bloqueantes, [f"{a.pagina}: {a.descricao}" for a in bloqueantes]
