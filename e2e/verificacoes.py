"""Verificações reutilizadas pelos testes: transformam medições em achados."""

import re
from pathlib import Path

from playwright.sync_api import Page

from e2e.ajudas import (
    medir_dialogo,
    medir_interativos,
    medir_overflow,
    textos_de_excecao,
)
from e2e.config import ALVO_MINIMO, estado_dados

PASTA_CAPTURAS = Path(__file__).parent / "capturas"

_MAX_ELEMENTOS_POR_TIPO = 12


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "pagina"


def verificar_layout(page: Page, cenario, registrar, nome_pagina: str) -> None:
    """Overflow do documento/contêineres e interativos fora do viewport ou pequenos."""
    overflow = medir_overflow(page)
    doc = overflow["documento"]
    if doc["scrollWidth"] > doc["clientWidth"] + 1:
        registrar(
            "P0",
            "overflow-horizontal",
            nome_pagina,
            "Documento rola na horizontal (scrollWidth > clientWidth).",
            "; ".join(c["el"] for c in overflow["culpados"][:3]),
            detalhe=f"{doc['scrollWidth']} > {doc['clientWidth']}",
        )
    for c in overflow["contenedores"]:
        registrar(
            "P0",
            "overflow-horizontal",
            nome_pagina,
            f"Contêiner {c['seletor']} rola na horizontal (scrollWidth > clientWidth).",
            "; ".join(x["el"] for x in overflow["culpados"][:3]),
            detalhe=f"{c['scrollWidth']} > {c['clientWidth']}",
        )
    for x in overflow["culpados"]:
        registrar(
            "P1",
            "elemento-fora-do-viewport",
            nome_pagina,
            "Elemento ultrapassa a largura da janela.",
            f"{x['el']} «{x['texto']}»",
            detalhe=f"esq. {x['esquerda']}, dir. {x['direita']}",
        )

    interativos = medir_interativos(page)
    for x in interativos["fora"][:_MAX_ELEMENTOS_POR_TIPO]:
        registrar(
            "P0",
            "interativo-fora-do-viewport",
            nome_pagina,
            "Controle fora da área visível.",
            f"{x['el']} «{x['rotulo']}»",
            detalhe=f"esq. {x['esquerda']}, dir. {x['direita']}",
        )
    for x in interativos["pequenos"][:_MAX_ELEMENTOS_POR_TIPO * 4]:
        registrar(
            "P1",
            "alvo-menor-que-44px",
            nome_pagina,
            f"Alvo menor que {ALVO_MINIMO}×{ALVO_MINIMO} px.",
            f"{x['el']} «{x['rotulo']}»",
            detalhe=f"{x['largura']}×{x['altura']}",
        )


def verificar_saude(page: Page, registrar, nome_pagina: str) -> None:
    """Exceções do Streamlit e erros de console."""
    for texto in textos_de_excecao(page):
        registrar("P0", "excecao-streamlit", nome_pagina, "Exceção exibida na página.", texto[:160].replace("\n", " "))
    erros = getattr(page, "erros_console", [])
    for erro in dict.fromkeys(erros):  # únicos, na ordem
        registrar("P2", "erro-console", nome_pagina, "Erro no console do navegador.", erro[:200])
    erros.clear()


def verificar_dialogo(page: Page, registrar, nome_pagina: str) -> None:
    """O diálogo aberto cabe na janela e mantém os botões alcançáveis."""
    d = medir_dialogo(page)
    if d is None:
        return
    caixa, vp = d["caixa"], d["viewport"]
    if caixa["esquerda"] < -1 or caixa["direita"] > vp["largura"] + 1:
        registrar(
            "P0",
            "dialogo-fora-da-largura",
            nome_pagina,
            f"Diálogo ultrapassa a largura ({caixa['esquerda']}–{caixa['direita']} de {vp['largura']}).",
        )
    altura = caixa["base"] - caixa["topo"]
    if (caixa["topo"] < -1 or caixa["base"] > vp["altura"] + 1) and not d["rola"]:
        registrar(
            "P0",
            "dialogo-sem-rolagem",
            nome_pagina,
            f"Diálogo de {altura}px não cabe em {vp['altura']}px de altura e não rola.",
        )
    for b in d["botoes"]:
        if b["esquerda"] < -1 or b["direita"] > vp["largura"] + 1:
            registrar(
                "P0",
                "dialogo-acao-fora-da-tela",
                nome_pagina,
                f"Botão «{b['rotulo']}» do diálogo fora da largura visível.",
            )


def capturar(page: Page, cenario, nome: str) -> None:
    pasta = PASTA_CAPTURAS / estado_dados() / cenario.perfil / cenario.tema / str(cenario.largura)
    pasta.mkdir(parents=True, exist_ok=True)
    # O Streamlit rola dentro de stMain, não no documento: full_page não capturaria o
    # conteúdo abaixo da dobra. Estica a janela até a altura do conteúdo só durante a foto.
    conteudo = page.evaluate(
        "() => { const m = document.querySelector('[data-testid=\"stMain\"]'); "
        "return m ? m.scrollHeight : document.documentElement.scrollHeight; }"
    )
    original = page.viewport_size
    try:
        page.set_viewport_size({"width": cenario.largura, "height": max(cenario.altura, min(conteudo, 12_000))})
        page.wait_for_timeout(300)
        page.screenshot(path=str(pasta / f"{_slug(nome)}.png"))
    finally:
        if original:
            page.set_viewport_size(original)
            page.wait_for_timeout(200)
