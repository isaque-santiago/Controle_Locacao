"""Fichas, painéis, faixas de dados e resumo dos relatórios (Plano de melhorias, Etapa 6)."""

from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.domain.relatorios import destaques
from src.ui.componentes import ficha_identidade, tabela_html

UI = Path(__file__).resolve().parents[1] / "src" / "ui"


def test_destaques_resume_total_e_extremos_em_decimal():
    resumo = destaques([("A", "10.10"), ("B", Decimal("-5.05")), ("C", 3)])
    assert resumo["quantidade"] == 3
    assert resumo["total"] == Decimal("8.05")
    assert resumo["maior"] == ("A", Decimal("10.10"))
    assert resumo["menor"] == ("B", Decimal("-5.05"))
    assert destaques([]) is None


def test_ficha_identidade_escapa_nada_alem_do_que_recebe_e_agrupa_marca_titulo_selo():
    html = ficha_identidade("Ana", selo="<b>x</b>", marca="<i>m</i>", subtitulo="sub")
    assert html.index("ficha-id__marca") < html.index("ficha-id__titulo") < html.index("ficha-id__sub") < html.index("ficha-id__selo")


def test_tabela_marca_a_ultima_celula_quando_o_numero_de_colunas_e_impar():
    def roteiro():
        from src.ui.componentes import tabela_html

        tabela_html(["A", "B", "C"], [["1", "2", "3"]], legenda="x")

    app = AppTest.from_function(roteiro).run()
    html = app.markdown[0].value
    assert html.count("celula--cheia") == 1
    assert html.index("celula--cheia") > html.index(">2<")


def test_fichas_usam_cabecalho_faixa_e_paineis_padrao():
    for nome in ("motos", "clientes", "contratos"):
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "cabecalho_ficha(" in codigo and "faixa_dados(" in codigo, nome
        assert 'st.columns([3, 1]' not in codigo.split("def _exibir_ficha")[-1], nome
    assert "paineis(" in (UI / "dashboard.py").read_text(encoding="utf-8")
    assert "st.columns(" not in (UI / "vistorias.py").read_text(encoding="utf-8")


def test_css_das_fichas_nao_depende_da_posicao_das_celulas():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    assert "nth-child" not in css
    assert "cartao--faixa" not in css and "dashboard_card_hoje" not in css
    assert "st-key-ficha_cabecalho" in css and "@container (max-width: 34rem)" in css
    assert "st-key-paineis_" in css and ".faixa-dados__valor" in css and "cqi" in css


def test_botao_voltar_da_lista_restaura_o_registro_uma_unica_vez():
    def roteiro():
        import streamlit as st

        from src.ui.listas import lembrar_registro, restaurar_posicao

        lembrar_registro("motos", "abc-123")
        restaurar_posicao("motos")
        st.session_state["depois"] = "motos_retorno" in st.session_state
        lembrar_registro("motos", "x'];alert(1);//")
        restaurar_posicao("motos")  # identificador inseguro: ignorado

    app = AppTest.from_function(roteiro).run()
    assert not app.exception
    assert app.session_state["depois"] is False
    assert "alert" not in str([e for e in app.get("html")])
