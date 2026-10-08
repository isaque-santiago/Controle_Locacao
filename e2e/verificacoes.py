"""Verificações reutilizadas pelos testes: transformam medições em achados."""

import re
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page

from e2e.ajudas import (
    medir_dialogo,
    medir_foco_por_teclado,
    medir_interativos,
    medir_overflow,
    medir_texto_cortado,
    textos_de_excecao,
)
from e2e.config import ALVO_MINIMO, estado_dados

PASTA_CAPTURAS = Path(__file__).parent / "capturas"

_MAX_ELEMENTOS_POR_TIPO = 12

# Impacto do axe-core -> (severidade do achado, tipo). Crítico e grave bloqueiam o aceite da Etapa 9.
_IMPACTO_AXE = {
    "critical": ("P0", "acessibilidade-critica"),
    "serious": ("P1", "acessibilidade-grave"),
    "moderate": ("P2", "acessibilidade-moderada"),
    "minor": ("INFO", "acessibilidade-leve"),
}
TIPOS_AXE_BLOQUEANTES = ("acessibilidade-critica", "acessibilidade-grave")

# WCAG 2.1 AA (mais as boas práticas do axe-core), sem as regras experimentais.
_OPCOES_AXE = {
    "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]},
    "resultTypes": ["violations"],
}


def achados_bloqueantes(coletor, cenario, *, pagina: str | None = None, fluxo: str | None = None) -> list:
    """Achados que reprovam o teste em modo estrito: todo P0 e as violações críticas/graves do axe."""
    return [
        a
        for a in coletor.achados
        if (a.severidade == "P0" or a.tipo in TIPOS_AXE_BLOQUEANTES)
        and a.largura == cenario.largura
        and a.perfil == cenario.perfil
        and a.tema == cenario.tema
        and (pagina is None or a.pagina == pagina)
        and (fluxo is None or a.fluxo == fluxo)
    ]


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "pagina"


def _esperar_assentar(page: Page) -> None:
    """Espera trocas do HTMX e transições de CSS terminarem.

    Sem isso o axe mede o contraste de um texto ainda semitransparente e acusa falso positivo."""
    try:
        page.wait_for_function(
            "() => !document.querySelector('.htmx-request, .htmx-swapping, .htmx-settling, .htmx-added')",
            timeout=8_000,
        )
    except Exception:
        pass
    page.wait_for_timeout(500)


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
    """Páginas de erro do app, respostas 5xx e erros de console."""
    for texto in textos_de_excecao(page):
        registrar("P0", "pagina-de-erro", nome_pagina, "Página de erro exibida.", " ".join(texto.split())[:160])
    falhas_http = getattr(page, "falhas_http", [])
    for falha in dict.fromkeys(falhas_http):
        registrar("P0", "resposta-5xx", nome_pagina, "O servidor respondeu com erro.", falha[:200])
    falhas_http.clear()
    erros = getattr(page, "erros_console", [])
    for erro in dict.fromkeys(erros):  # únicos, na ordem
        registrar("P2", "erro-console", nome_pagina, "Erro no console do navegador.", erro[:200])
    erros.clear()


def verificar_acessibilidade(page: Page, registrar, nome_pagina: str) -> None:
    """Auditoria automatizada (axe-core): uma ocorrência por regra violada na tela atual."""
    _esperar_assentar(page)
    antes = len(getattr(page, "erros_console", []))
    try:
        resultado = Axe().run(page, options=_OPCOES_AXE)
    except Exception as erro:  # a auditoria nunca derruba o fluxo; vira achado
        registrar("P2", "axe-indisponivel", nome_pagina, f"Falha ao rodar o axe-core: {type(erro).__name__}")
        return
    # O axe aplica estilos inline temporários e a CSP (style-src 'self') os recusa com um erro de console
    # (hash de texto vazio). É efeito da ferramenta, não da página: não conta como erro do app.
    page.wait_for_timeout(250)
    erros = getattr(page, "erros_console", [])
    do_axe = [e for e in erros[antes:] if "Content Security Policy" in e and "style-src" in e]
    if do_axe:
        erros[:] = [e for e in erros if e not in do_axe]
        registrar("INFO", "csp-style-do-axe", nome_pagina, "Erro de CSP de estilo causado pelo próprio axe-core (ignorado).")
    for v in resultado.response["violations"]:
        severidade, tipo = _IMPACTO_AXE.get(v.get("impact") or "minor", ("INFO", "acessibilidade-leve"))
        alvos = [" ".join(n["target"]) if isinstance(n["target"], list) else str(n["target"]) for n in v["nodes"]]
        registrar(
            severidade,
            tipo,
            nome_pagina,
            f"{v['help']} ({v['id']})",
            alvos[0][:160],
            detalhe=f"{len(v['nodes'])} elemento(s)",
        )


def verificar_teclado(page: Page, registrar, nome_pagina: str, maximo: int = 60) -> list[str]:
    """Percorre a página só com Tab: foco visível, dentro da janela, com nome acessível e sem armadilha.

    Devolve a sequência de paradas (rótulos), usada pelo registro da homologação para conferir a ordem."""
    medir_foco_por_teclado(page, "iniciar")
    paradas: list[str] = []
    ultimo = None
    repetidos = 0
    for _ in range(maximo):
        page.keyboard.press("Tab")
        page.wait_for_timeout(120)  # o WebKit rola o elemento para a vista depois do foco
        p = medir_foco_por_teclado(page, "ler")
        if p is None:
            break
        if p["chave"] == ultimo:
            if p.get("ultimo"):
                break  # saiu da página pelo fim (Firefox mantém o último elemento focado)
            repetidos += 1
            if repetidos >= p.get("segmentos", 1) + 1:
                registrar("P0", "armadilha-de-teclado", nome_pagina, "O foco não avança com Tab.", p["el"])
                break
            continue
        repetidos = 0
        ultimo = p["chave"]
        paradas.append(p["rotulo"] or p["el"])
        if p["fim_do_documento"]:
            break
        if not p["indicador"]:
            registrar("P1", "foco-invisivel", nome_pagina, "Elemento focado sem indicador visível.", f"{p['el']} «{p['rotulo']}»")
        if not p["dentro"]:
            # Parcialmente visível (o WebKit deixa o campo rente à borda inferior) é P2: conferir em iPhone/iPad reais.
            severidade = "P2" if p.get("parcial") else "P1"
            registrar(severidade, "foco-fora-da-janela", nome_pagina, "Elemento focado fora da área visível.", f"{p['el']} «{p['rotulo']}»")
        if not p["rotulo"] and "main#conteudo" not in p["el"]:  # a região principal é um marco, não um controle
            registrar("P1", "foco-sem-nome", nome_pagina, "Elemento focável sem nome acessível.", p["el"])
        if p["regressao"]:
            registrar(
                "P2",
                "ordem-de-foco",
                nome_pagina,
                "O foco volta para cima na página (ordem pouco lógica).",
                f"{p['el']} «{p['rotulo']}»",
                detalhe=f"{p['regressao']}px",
            )
    return paradas


def verificar_texto_cortado(page: Page, registrar, nome_pagina: str) -> None:
    """Texto cortado por contêiner com overflow oculto (texto a 200% e espaçamento WCAG)."""
    for x in medir_texto_cortado(page)[:_MAX_ELEMENTOS_POR_TIPO]:
        registrar(
            "P1",
            "texto-cortado",
            nome_pagina,
            "Conteúdo cortado: o contêiner esconde o que não cabe.",
            f"{x['el']} «{x['texto']}»",
            detalhe=f"{x['conteudo']}×{x['caixa']} px",
        )


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


def capturar(page: Page, cenario, nome: str, pasta_base: Path = PASTA_CAPTURAS, variante: str = "") -> Path:
    """Foto da página inteira. Devolve o caminho do PNG.

    `variante` separa fotos de condições extras (zoom, paisagem…) das da matriz principal."""
    pasta = pasta_base / estado_dados() / cenario.perfil / cenario.tema / (variante or str(cenario.largura))
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{_slug(nome)}.png"
    # O documento rola (não há contêiner interno): a foto de página inteira cobre o conteúdo abaixo da dobra.
    page.wait_for_timeout(300)
    page.screenshot(path=str(destino), full_page=True)
    return destino
