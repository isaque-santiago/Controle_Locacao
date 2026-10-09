"""Condições extras da matriz da Etapa 9, além das 5 larguras × 2 temas.

- zoom de 200% no desktop (1440×900 vira 720×450 px CSS) e reflow a 320 px CSS (400% de zoom);
- celular em paisagem;
- texto a 200% e espaçamento de texto da WCAG 1.4.12;
- rede e CPU reduzidas (só Chromium, pelo protocolo de depuração).

Cada condição percorre todas as páginas e mede overflow, alvos, texto cortado e erros. Roda uma
vez por perfil e tema (na largura de referência do perfil), com os dados do estado `E2E_DADOS`."""

import time

import pytest

from e2e.ajudas import ir_para, tem_formulario_login
from e2e.config import PAGINAS, PERFIS
from e2e.verificacoes import (
    achados_bloqueantes,
    capturar,
    verificar_layout,
    verificar_saude,
    verificar_teclado,
    verificar_texto_cortado,
)

pytestmark = pytest.mark.autenticado

_CSS_TEXTO_200 = "html {font-size: 200% !important;}"
# WCAG 1.4.12: altura de linha 1,5, espaço entre parágrafos 2×, entre letras 0,12× e entre palavras 0,16×.
_CSS_ESPACAMENTO = (
    "* {line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important;}"
    " p {margin-bottom: 2em !important;}"
)

# nome: (largura, altura, CSS extra)
VARIANTES = {
    "zoom-200": (720, 450, ""),
    "reflow-400": (320, 256, ""),
    "paisagem-celular": (844, 390, ""),
    "texto-200": (1024, 768, _CSS_TEXTO_200),
    "espacamento-wcag-celular": (390, 844, _CSS_ESPACAMENTO),
    "espacamento-wcag-desktop": (1440, 900, _CSS_ESPACAMENTO),
}

# Cada perfil roda as variantes uma vez por tema, na largura de referência dele.
_LARGURA_REFERENCIA = {"chromium-movel": 390}
_LARGURA_REFERENCIA_PADRAO = 1440

# Acima disto a carga, mesmo com rede e CPU reduzidas, vira achado.
_LIMITE_CARGA_REDUZIDA_S = 45


def _aplicar_css(page, css: str) -> None:
    """Aplica CSS pelo CSSOM (folha construída): a CSP do app (style-src 'self') recusa <style> inline."""
    page.evaluate(
        "css => { const f = new CSSStyleSheet(); f.replaceSync(css); document.adoptedStyleSheets = [...document.adoptedStyleSheets, f]; }",
        css,
    )


def _roda_nesta_largura(cenario) -> bool:
    return cenario.largura == _LARGURA_REFERENCIA.get(cenario.perfil, _LARGURA_REFERENCIA_PADRAO)


@pytest.mark.parametrize("variante", list(VARIANTES))
def test_variante(variante, pagina_logada, cenario, registrar, coletor, request):
    if not _roda_nesta_largura(cenario):
        pytest.skip("variantes rodam só na largura de referência do perfil")
    largura, altura, css = VARIANTES[variante]
    reg = registrar(cenario, fluxo=f"homologacao-{variante}")
    page = pagina_logada
    capturas = request.config.getoption("--capturas")
    original = page.viewport_size
    page.set_viewport_size({"width": largura, "height": altura})
    try:
        for pagina in PAGINAS:
            try:
                ir_para(page, pagina)
            except Exception as erro:
                reg("P0", "pagina-nao-carrega", pagina.titulo, f"Falha ao abrir: {type(erro).__name__}")
                continue
            if tem_formulario_login(page):
                reg("P0", "sessao-perdida", pagina.titulo, "A navegação voltou para a tela de acesso.")
                continue
            if css:
                _aplicar_css(page, css)
                page.wait_for_timeout(400)
            verificar_layout(page, cenario, reg, f"{pagina.titulo} ({variante})")
            verificar_texto_cortado(page, reg, f"{pagina.titulo} ({variante})")
            verificar_saude(page, reg, f"{pagina.titulo} ({variante})")
            if capturas:
                capturar(page, cenario, pagina.titulo, variante=variante)
    finally:
        if original:
            page.set_viewport_size(original)

    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, fluxo=f"homologacao-{variante}")
        assert not bloqueantes, [f"{a.pagina}: {a.descricao}" for a in bloqueantes]


def test_teclado_em_todas_as_paginas(pagina_logada, cenario, registrar, coletor, request):
    """Fluxo só de teclado: foco visível, ordem lógica, nomes e ausência de armadilhas."""
    if not _roda_nesta_largura(cenario):
        pytest.skip("roda só na largura de referência do perfil")
    reg = registrar(cenario, fluxo="homologacao-teclado")
    for pagina in PAGINAS:
        try:
            ir_para(pagina_logada, pagina)
        except Exception as erro:
            reg("P0", "pagina-nao-carrega", pagina.titulo, f"Falha ao abrir: {type(erro).__name__}")
            continue
        paradas = verificar_teclado(pagina_logada, reg, pagina.titulo, maximo=120)
        reg(
            "INFO",
            "ordem-de-tabulacao",
            pagina.titulo,
            f"{len(paradas)} paradas de Tab; primeiras: " + " → ".join(paradas[:14]),
        )
    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, fluxo="homologacao-teclado")
        assert not bloqueantes, [f"{a.pagina}: {a.descricao}" for a in bloqueantes]


def test_rede_e_cpu_reduzidas(pagina_logada, cenario, registrar, coletor, request):
    """Carrega cada página com CPU 4× mais lenta e rede de ~1,6 Mbps / 150 ms (só Chromium)."""
    if PERFIS[cenario.perfil].navegador != "chromium":
        pytest.skip("o estrangulamento usa o protocolo de depuração do Chromium")
    if not _roda_nesta_largura(cenario) or cenario.tema != "claro":
        pytest.skip("uma medição por perfil basta (tema não muda o peso da página)")
    reg = registrar(cenario, fluxo="homologacao-rede-cpu")
    page = pagina_logada
    sessao = page.context.new_cdp_session(page)
    sessao.send("Network.enable")
    sessao.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    sessao.send(
        "Network.emulateNetworkConditions",
        {"offline": False, "latency": 150, "downloadThroughput": 200_000, "uploadThroughput": 93_750},
    )
    try:
        for pagina in PAGINAS:
            inicio = time.monotonic()
            try:
                ir_para(page, pagina)
            except Exception as erro:
                reg("P1", "carga-reduzida-falhou", pagina.titulo, f"Não terminou de carregar: {type(erro).__name__}")
                continue
            segundos = time.monotonic() - inicio
            severidade = "P1" if segundos > _LIMITE_CARGA_REDUZIDA_S else "INFO"
            reg(
                severidade,
                "carga-com-rede-e-cpu-reduzidas",
                pagina.titulo,
                "Tempo até a página ficar utilizável (CPU 4×, ~1,6 Mbps, 150 ms).",
                detalhe=f"{segundos:.1f} s",
            )
            verificar_saude(page, reg, pagina.titulo)
    finally:
        sessao.send("Emulation.setCPUThrottlingRate", {"rate": 1})
        sessao.send(
            "Network.emulateNetworkConditions",
            {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1},
        )
        sessao.detach()
