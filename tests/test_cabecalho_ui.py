"""Cabeçalho de página e estados vazios (Plano de melhorias, Etapa 2)."""

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.ui.componentes import estado_vazio, vazio_lista

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"


def _roteiro_com_acao():
    import streamlit as st

    from src.ui.componentes import cabecalho_pagina

    clicou = cabecalho_pagina(
        "Motos",
        sub="2 moto(s) cadastrada(s)",
        acao={"rotulo": "Nova moto", "chave": "motos_nova", "ajuda": "Cadastrar uma moto"},
    )
    st.write(f"clicou={clicou}")


def test_cabecalho_com_acao_cria_um_botao_primario_com_icone():
    app = AppTest.from_function(_roteiro_com_acao).run()
    assert not app.exception
    botoes = list(app.button)
    assert [b.label for b in botoes] == ["Nova moto"]  # no máximo uma ação primária
    assert botoes[0].key == "motos_nova" and botoes[0].help == "Cadastrar uma moto"
    assert "Motos" in app.markdown[0].value and "2 moto(s) cadastrada(s)" in app.markdown[0].value
    assert app.markdown[1].value == "clicou=False"


def test_cabecalho_devolve_true_quando_a_acao_e_clicada():
    app = AppTest.from_function(_roteiro_com_acao).run()
    app.button[0].click().run()
    assert app.markdown[1].value == "clicou=True"


def test_cabecalho_sem_acao_nao_cria_botao():
    def roteiro():
        from src.ui.componentes import cabecalho_pagina

        cabecalho_pagina("Cobranças", sub="Nenhuma cobrança em atraso")

    app = AppTest.from_function(roteiro).run()
    assert not app.exception and not list(app.button)
    assert "painel-cabecalho" in app.markdown[0].value


def test_cabecalho_com_acao_dentro_de_formulario_usa_botao_de_envio():
    def roteiro():
        import streamlit as st

        from src.ui.componentes import cabecalho_pagina

        with st.form("f", border=False):
            salvar = cabecalho_pagina(
                "Configurações",
                sub="Parâmetros do sistema",
                acao={"rotulo": "Salvar alterações", "chave": "salvar", "formulario": True},
            )
        st.write(f"salvou={salvar}")

    app = AppTest.from_function(roteiro).run()
    assert not app.exception
    app.button[0].click().run()
    assert app.markdown[-1].value == "salvou=True"


def test_cabecalho_escapa_o_titulo():
    def roteiro():
        from src.ui.componentes import cabecalho_pagina

        cabecalho_pagina("<b>Olá</b>")

    app = AppTest.from_function(roteiro).run()
    assert "&lt;b&gt;" in app.markdown[0].value


def test_nenhuma_pagina_monta_o_cabecalho_na_mao():
    """As páginas usam `cabecalho_pagina`; o h1 da página só nasce em componentes.py."""
    ofensores = [
        f"{arquivo.name}: {linha.strip()}"
        for arquivo in UI.glob("*.py")
        if arquivo.name != "componentes.py"
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if "pagina-titulo" in linha
    ]
    assert not ofensores, ofensores


def test_todas_as_paginas_de_lista_usam_o_cabecalho_padrao():
    for nome in (
        "motos", "clientes", "contratos", "manutencao", "documentos", "vistorias",
        "cobrancas", "relatorios", "configuracoes", "portal_locatario", "dashboard",
    ):
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "cabecalho_pagina(" in codigo, nome


def test_botoes_de_cabecalho_nao_usam_mais_sinal_de_mais_no_rotulo():
    padrao = re.compile(r'"rotulo":\s*"\+')
    for arquivo in UI.glob("*.py"):
        assert not padrao.search(arquivo.read_text(encoding="utf-8")), arquivo.name


def test_css_posiciona_a_acao_e_a_leva_para_baixo_no_contorno_estreito():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    assert ".st-key-pagina_cabecalho" in css
    assert "container-type: inline-size" in css
    assert "@container (max-width:" in css


def test_estado_vazio_compacto_mostra_motivo_e_proximo_passo():
    html = estado_vazio("Nenhuma moto encontrada.", "Limpe a busca.", compacto=True)
    assert "Nenhuma moto encontrada." in html and "Limpe a busca." in html


def test_vazio_lista_explica_o_motivo_conforme_haja_ou_nao_registros():
    filtrado = vazio_lista("Nenhuma moto encontrada.", "Ainda não há motos cadastradas.", True, "Nova moto")
    assert "Nenhuma moto encontrada." in filtrado and "filtro ou a busca" in filtrado
    assert "Ainda não há" not in filtrado

    sem_registros = vazio_lista("Nenhuma moto encontrada.", "Ainda não há motos cadastradas.", False, "Nova moto")
    assert "Ainda não há motos cadastradas." in sem_registros
    assert "Nova moto" in sem_registros  # próximo passo: a ação do cabeçalho

    sem_acao = vazio_lista("x", "Ainda não há itens.", False)
    assert "Use" not in sem_acao
