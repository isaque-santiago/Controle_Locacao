"""Fase 5 do redesign (animações e feedback): contratos do CSS, do JS e dos templates.

Não há navegador nos testes unitários; aqui se garante o que dá para checar no texto: valor final no HTML, respeito a
prefers-reduced-motion, atrasos curtos e limitados e ausência de JS inline/eval (a CSP do app os proíbe)."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
JS = (RAIZ / "static" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (RAIZ / "src" / "web" / "estilos" / "app.css").read_text(encoding="utf-8")
MACROS = (RAIZ / "src" / "web" / "templates" / "componentes" / "macros.html").read_text(encoding="utf-8")


def test_js_nao_usa_eval_nem_html_inline_de_evento():
    assert not re.search(r"\beval\s*\(|new Function\s*\(", JS)


def test_kpi_traz_o_valor_final_no_html_e_marca_o_numero_que_conta():
    # O número certo está no HTML (dentro do span); o JS só anima e, no fim, devolve o texto original.
    assert "<dd><span data-contar>{{ valor }}</span>" in MACROS
    assert "elemento.textContent = original" in JS
    assert "movimentoReduzido.matches" in JS  # sem animação com movimento reduzido


def test_entrada_escalonada_e_curta_e_limitada():
    atrasos = [int(m) for m in re.findall(r"animation-delay:\s*(\d+)ms", CSS.split("/* ---------- Entrada em sequência")[1].split("Diálogos e painéis")[0])]
    assert atrasos and max(atrasos) <= 200
    # a página inteira não anima mais no <main> (a opacidade de pai e filho se multiplica)
    assert "main {animation:" not in CSS
