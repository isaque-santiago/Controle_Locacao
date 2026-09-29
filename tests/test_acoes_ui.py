"""Ações da interface (Plano de melhorias, Etapa 1): texto real, ícone do mesmo conjunto e alvo de 44 px."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.ui.componentes import ACOES

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"
# Pictogramas que, sozinhos ou como parte do rótulo, deixariam a ação dependente de tooltip
_SIMBOLOS = "→✓✎›‹↗"


def test_todas_as_acoes_tem_texto_e_icone_material():
    for nome, (texto, icone) in ACOES.items():
        assert texto.strip() and not any(s in texto for s in _SIMBOLOS), nome
        assert re.fullmatch(r":material/[a-z_]+:", icone), nome


def test_nenhum_botao_usa_simbolo_unicode_no_rotulo():
    """Ícones vêm do parâmetro `icon=`; o rótulo é texto."""
    padrao = re.compile(r"\.button\(\s*f?[\"'][^\"']*[" + _SIMBOLOS + r"]")
    ofensores = [
        f"{arquivo.name}: {linha.strip()}"
        for arquivo in UI.glob("*.py")
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if padrao.search(linha)
    ]
    assert not ofensores, ofensores


def test_botao_acao_cria_botao_terciario_com_icone_e_ajuda():
    def roteiro():
        import streamlit as st

        from src.ui.componentes import botao_acao

        botao_acao(st, "pagar", "pagar_x", ajuda="Registrar o pagamento de Ana")
        botao_acao(st, "editar", "editar_x", desabilitado=True)

    app = AppTest.from_function(roteiro).run()
    assert not app.exception
    pagar = next(b for b in app.button if b.key == "pagar_x")
    assert pagar.label == "Pagar"
    assert pagar.help == "Registrar o pagamento de Ana"
    editar = next(b for b in app.button if b.key == "editar_x")
    assert editar.label == "Editar" and editar.disabled


def test_botao_voltar_informa_o_destino():
    def roteiro():
        from src.ui.componentes import botao_voltar

        botao_voltar("motos", "voltar_motos")

    app = AppTest.from_function(roteiro).run()
    assert next(b for b in app.button if b.key == "voltar_motos").label == "Voltar para motos"


@pytest.mark.parametrize("arquivo", ["estilos.css"])
def test_css_define_alvo_minimo_de_44px_e_nao_reduz_botoes(arquivo):
    css = (UI / arquivo).read_text(encoding="utf-8")
    assert "--alvo-min: 44px;" in css
    # Nenhuma regra de botão volta a fixar altura/largura menor que o alvo mínimo
    for numero, linha in enumerate(css.splitlines(), start=1):
        if "button" in linha and re.search(r"(min-)?(width|height):\s*(3\dpx|2rem\b|1\.75rem)", linha):
            pytest.fail(f"{arquivo}:{numero} reduz um botão abaixo de 44 px: {linha.strip()}")
