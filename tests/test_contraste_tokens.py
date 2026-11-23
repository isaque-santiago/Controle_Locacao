"""Contraste mínimo de 4,5:1 (WCAG 1.4.3) dos pares texto/fundo definidos pelos tokens do design system.

Lê as variáveis CSS de src/web/estilos/app.css (bloco `:root`: cada cor é `light-dark(claro, escuro)`)
e confere os pares que o app realmente usa. A auditoria no navegador (axe-core, Etapa 9) cobre o que é
renderizado; este teste pega a regressão de token antes de abrir o navegador."""

import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[1] / "src" / "web" / "estilos" / "app.css"
_VAR = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")
_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")
_RGBA = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$")

MINIMO = 4.5


def _argumentos(texto: str) -> list[str]:
    """Divide os argumentos de nível zero de uma função CSS (`a, rgba(1,2,3,.4)` -> 2 itens)."""
    itens, fundo, atual = [], 0, ""
    for ch in texto:
        if ch == "(":
            fundo += 1
        elif ch == ")":
            fundo -= 1
        if ch == "," and fundo == 0:
            itens.append(atual.strip())
            atual = ""
        else:
            atual += ch
    itens.append(atual.strip())
    return itens


def _resolver(valor: str, bruto: dict[str, str], escuro: bool) -> str:
    """Resolve `light-dark(claro, escuro)` e `var(--x)` de um valor, para o tema pedido."""
    valor = valor.strip()
    if valor.startswith("light-dark(") and valor.endswith(")"):
        claro, noite = _argumentos(valor[len("light-dark(") : -1])
        return _resolver(noite if escuro else claro, bruto, escuro)
    m = re.fullmatch(r"var\(--([a-z0-9-]+)\)", valor)
    if m:
        return _resolver(bruto[m.group(1)], bruto, escuro)
    return valor


def _tokens(tema: str) -> dict[str, str]:
    """Tokens do bloco `:root` (cada cor é definida uma vez, como light-dark(claro, escuro)) já resolvidos para o tema."""
    texto = CSS.read_text(encoding="utf-8")
    inicio = texto.index(":root {")
    bloco = texto[inicio : texto.index("\n}", inicio)]
    bruto = {nome: valor.strip() for nome, valor in _VAR.findall(bloco)}
    return {nome: _resolver(valor, bruto, tema == "escuro") for nome, valor in bruto.items()}


def _cor(valor: str) -> tuple[float, float, float, float]:
    m = _HEX.match(valor)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    m = _RGBA.match(valor)
    assert m, f"cor não reconhecida: {valor}"
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4) or 1)


def _sobre(frente: tuple, fundo: tuple) -> tuple[float, float, float, float]:
    """Compõe uma cor com transparência sobre um fundo opaco."""
    a = frente[3]
    return tuple(frente[i] * a + fundo[i] * (1 - a) for i in range(3)) + (1.0,)


def _luminancia(c: tuple) -> float:
    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(c[0]) + 0.7152 * canal(c[1]) + 0.0722 * canal(c[2])


def contraste(texto: tuple, fundo: tuple) -> float:
    a, b = _luminancia(texto), _luminancia(fundo)
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


@pytest.fixture(scope="module", params=["claro", "escuro"])
def tema(request):
    return request.param, _tokens(request.param)


_SUPERFICIES = ("fundo", "superficie", "superficie-elevada")
_ESTADOS = ("sucesso", "alerta", "perigo", "info", "neutro")


def test_texto_principal_e_secundario_sobre_as_superficies(tema):
    nome, t = tema
    for texto in ("texto", "texto-2"):
        for sup in _SUPERFICIES:
            razao = contraste(_cor(t[texto]), _cor(t[sup]))
            assert razao >= MINIMO, f"{nome}: --{texto} sobre --{sup} = {razao:.2f}:1"


def test_texto_terciario_sobre_as_superficies(tema):
    """O terciário (rótulos, etapas futuras) também aparece direto sobre o fundo da página."""
    nome, t = tema
    for sup in _SUPERFICIES:
        razao = contraste(_cor(t["texto-3"]), _cor(t[sup]))
        assert razao >= MINIMO, f"{nome}: --texto-3 sobre --{sup} = {razao:.2f}:1"


@pytest.mark.parametrize("estado", _ESTADOS)
def test_selos_de_estado_tem_contraste(tema, estado):
    """Texto do selo (`--<estado>-texto`) sobre o fundo translúcido dele, composto sobre cada superfície."""
    nome, t = tema
    for sup in _SUPERFICIES:
        base = _cor(t[sup])
        fundo = _sobre(_cor(t[f"{estado}-fundo"]), base)
        razao = contraste(_cor(t[f"{estado}-texto"]), fundo)
        assert razao >= MINIMO, f"{nome}: selo {estado} sobre --{sup} = {razao:.2f}:1"


def test_botao_primario(tema):
    nome, t = tema
    razao = contraste(_cor(t["btn-texto"]), _cor(t["btn"]))
    assert razao >= MINIMO, f"{nome}: texto do botão primário = {razao:.2f}:1"
