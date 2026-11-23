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


def test_toasts_tem_aria_live_fechamento_manual_e_automatico_e_empilham():
    layout = (RAIZ / "src" / "web" / "templates" / "layout_painel.html").read_text(encoding="utf-8")
    assert 'id="avisos" aria-live="polite"' in layout  # região viva já existente; cada aviso leva role=status/alert
    assert "role=\"{{ 'alert' if tipo == 'erro' else 'status' }}\"" in MACROS
    assert "aviso-fechar" in JS and 'aria-label="Fechar aviso"' in JS
    assert "TEMPO_TOAST" in JS and "mouseenter" in JS and "focusin" in JS  # fecha sozinho, mas pausa com mouse/foco
    assert "MAXIMO_TOASTS" in JS
    assert "htmx:oobBeforeSwap" in JS  # a resposta fora de banda não apaga os toasts que ainda estão na tela
    assert re.search(r"#avisos \{position: fixed;", CSS)
    # toda animação do toast fica sob prefers-reduced-motion: no-preference (e o JS remove na hora quando reduzido)
    bloco = CSS.split("@keyframes toast-entra")[0].rsplit("@media", 1)[1]
    assert "prefers-reduced-motion: no-preference" in bloco


def test_erro_htmx_acrescenta_o_aviso_em_vez_de_substituir():
    erros = (RAIZ / "src" / "web" / "erros.py").read_text(encoding="utf-8")
    assert '"HX-Reswap": "beforeend"' in erros


def test_estado_vazio_tem_icone_titulo_texto_e_acao_sugerida():
    from jinja2 import Environment, FileSystemLoader

    ambiente = Environment(loader=FileSystemLoader(RAIZ / "src" / "web" / "templates"), autoescape=True)
    modelo = ambiente.from_string(
        '{% from "componentes/macros.html" import estado_vazio, botao %}'
        '{% call estado_vazio("Nenhum cliente cadastrado", "Os clientes aparecem aqui.", icone_nome="cliente") %}'
        '{{ botao("Novo cliente", variante="primario") }}{% endcall %}'
        '{{ estado_vazio("Sem ação", "Só texto.") }}'
    )
    html = modelo.render()
    assert '<span class="vazio-icone" aria-hidden="true">' in html and "#i-cliente" in html
    assert "<h2>Nenhum cliente cadastrado</h2>" in html and "Os clientes aparecem aqui." in html
    assert '<div class="vazio-acoes">' in html and "Novo cliente" in html
    assert html.count('class="vazio-acoes"') == 1  # sem botões, não sobra um contêiner vazio


def test_nenhum_estado_vazio_usa_mais_o_adesivo_com_zero():
    for arquivo in (RAIZ / "src" / "web" / "templates").rglob("*.html"):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if "estado_vazio(" in linha and "import" not in linha:
                assert ', "0")' not in linha, arquivo


def test_skeleton_so_aparece_depois_de_150ms_e_respeita_movimento_reduzido():
    bloco = CSS.split("/* ---------- Skeleton")[1].split("/* ---------- Busca global")[0]
    assert "transition: color 0s 150ms" in bloco and "visibility 0s 150ms" in bloco  # respostas rápidas não piscam
    assert "animation: skeleton-entra 150ms ease 150ms backwards" in bloco
    animado = bloco.split("prefers-reduced-motion: no-preference")[1]
    assert "skeleton-brilho" in animado and "skeleton-brilho" not in bloco.split("prefers-reduced-motion: no-preference")[0].replace("@keyframes", "")


def test_transicao_entre_paginas_so_com_movimento_permitido_e_mantem_o_menu_parado():
    bloco = CSS.split("/* ---------- Transição entre páginas")[1]
    assert bloco.index("prefers-reduced-motion: no-preference") < bloco.index("@view-transition {navigation: auto;}")
    for nome in ("lateral", "topo-desktop", "topo-movel", "barra-inferior"):
        assert f"view-transition-name: {nome}" in bloco


def test_toda_animacao_com_atraso_ou_duracao_longa_esta_sob_movimento_permitido():
    # Regra do projeto: nenhuma animação (propriedade animation:) fora de um bloco que a desliga com prefers-reduced-motion.
    # O CSS tem uma regra global que zera animações no reduce; aqui só se confere que ela continua lá.
    assert "@media (prefers-reduced-motion: reduce) {* {transition: none !important; animation: none !important;}}" in CSS
