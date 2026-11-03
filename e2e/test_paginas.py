"""Fluxo 1 (Entrar e navegar por todas as páginas): linha de base de cada tela."""

import pytest

from e2e.ajudas import aguardar_app, ir_para, tem_formulario_login
from e2e.config import PAGINAS, base_url
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


def test_entrar_e_sair(pagina_nova_sessao, cenario, registrar, coletor, request):
    """Fluxo 1, parte final: sair encerra a sessão (no celular o botão fica na folha «Mais»)."""
    from e2e.roteiro import grava_neste_cenario

    if not grava_neste_cenario(cenario):
        pytest.skip("um login extra por perfil basta")
    reg = registrar(cenario, fluxo="01-entrar-e-navegar")
    page = pagina_nova_sessao
    sair = page.get_by_role("button", name="Sair").locator("visible=true")
    if not sair.count():
        page.get_by_role("button", name="Mais").click()
        sair = page.get_by_role("button", name="Sair").locator("visible=true")
    sair.first.click()
    aguardar_app(page)
    if not tem_formulario_login(page):
        reg("P0", "logout-nao-leva-ao-login", "Sair", "Depois de «Sair» a tela de acesso não apareceu.")
    page.goto(base_url() + "/")
    aguardar_app(page)
    if not tem_formulario_login(page):
        reg("P0", "sessao-nao-encerrou", "Sair", "A página inicial abriu depois de sair: a sessão continua válida.")
    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, pagina="Sair")
        assert not bloqueantes, [a.descricao for a in bloqueantes]
