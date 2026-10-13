"""Regressão visual da tela de acesso e das páginas autenticadas contra a referência aprovada.

Primeira execução (ou `--atualizar-referencia`): grava a referência. Depois: compara e reprova se
mais de `--tolerancia-visual` % dos pixels mudarem. Veja e2e/visual.py.

ATENÇÃO: as telas mostram os dados do banco de desenvolvimento, e os fluxos 4 a 10 os alteram (pagamentos, contratos,
documentos…). Grave a referência e compare SEMPRE com o banco no mesmo estado: depois de recriar o banco de dev e antes de
rodar os fluxos (`-k visual`). Os testes de visual têm "visual" no nome para os outros comandos poderem excluí-los."""

import pytest

from e2e.ajudas import abrir_login, ir_para, tem_formulario_login
from e2e.config import PAGINAS
from e2e.verificacoes import _esperar_assentar, capturar
from e2e.visual import PASTA_ATUAL, comparar


def _conferir(page, cenario, nome, request) -> str | None:
    _esperar_assentar(page)
    atual = capturar(page, cenario, nome, pasta_base=PASTA_ATUAL)
    aprovado, mensagem = comparar(
        atual, request.config.getoption("--tolerancia-visual"), request.config.getoption("--atualizar-referencia")
    )
    return None if aprovado else f"{nome}: {mensagem}"


def test_visual_login(pagina_anonima, cenario, request):
    abrir_login(pagina_anonima)
    assert tem_formulario_login(pagina_anonima)
    falha = _conferir(pagina_anonima, cenario, "login", request)
    assert falha is None, falha


@pytest.mark.autenticado
def test_visual_das_telas(pagina_logada, cenario, request):
    falhas = []
    for pagina in PAGINAS:
        ir_para(pagina_logada, pagina)
        falha = _conferir(pagina_logada, cenario, pagina.titulo, request)
        if falha:
            falhas.append(falha)
    assert not falhas, falhas
