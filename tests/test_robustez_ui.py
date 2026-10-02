"""Etapa 8: robustez do CSS (sem inversão de dataframe, sem nth-child, fontes com fallback, sem estilo inline)."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "src" / "ui"
CLARO = (UI / "estilos.css").read_text(encoding="utf-8")
ESCURO = (UI / "estilos_escuro.css").read_text(encoding="utf-8")


def test_sem_nth_child_nos_estilos():
    assert "nth-child" not in CLARO
    assert "nth-child" not in ESCURO


def test_modo_escuro_sem_filtro_de_inversao():
    assert "invert(" not in ESCURO
    assert "hue-rotate" not in ESCURO
    assert "stDataFrame" not in CLARO + ESCURO


def test_fontes_tem_fallback_do_sistema():
    for token in ("--fonte-titulo", "--fonte-ui", "--fonte-mono"):
        linha = next(l for l in CLARO.splitlines() if l.strip().startswith(token + ":"))
        assert linha.count(",") >= 2, linha
        assert re.search(r"(sans-serif|monospace);", linha), linha


# Valores calculados (largura de barra/flex de segmento, cor de avatar) são os únicos `style=` aceitos.
_PERMITIDO = re.compile(r'style="(width:\{[^"]*\}%|flex:\{q\}|background:\{[a-z_]+\};|min-width:11rem;padding:0;|margin:\.6rem 0 \.5rem;)"')


def test_paginas_sem_estilo_inline_estatico():
    achados = []
    for arq in sorted(UI.glob("*.py")):
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r'style="[^"]*"', linha):
                if not _PERMITIDO.fullmatch(m.group(0)):
                    achados.append(f"{arq.name}:{n}: {m.group(0)}")
    assert not achados, "\n".join(achados)
