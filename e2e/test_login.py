"""Tela de acesso: única tela testável sem credenciais."""

from e2e.ajudas import abrir_login, tem_formulario_login
from e2e.verificacoes import (
    achados_bloqueantes,
    capturar,
    verificar_acessibilidade,
    verificar_layout,
    verificar_saude,
    verificar_teclado,
)


def test_login_sem_overflow_e_alcancavel(pagina_anonima, cenario, registrar, coletor, request):
    reg = registrar(cenario, fluxo="01-entrar-e-navegar")
    page = pagina_anonima

    abrir_login(page)
    assert tem_formulario_login(page), "a tela de acesso deveria exibir o botão 'Entrar no painel'"

    verificar_layout(page, cenario, reg, "Login")
    verificar_saude(page, reg, "Login")
    verificar_acessibilidade(page, reg, "Login")
    verificar_teclado(page, reg, "Login")
    if request.config.getoption("--capturas"):
        capturar(page, cenario, "login")

    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, pagina="Login")
        assert not bloqueantes, [a.descricao for a in bloqueantes]
