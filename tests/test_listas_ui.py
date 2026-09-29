"""Filtros, busca, paginação e abas das listas (Plano de melhorias, Etapa 3)."""

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"


def _texto(app):
    return " ".join(m.value for m in app.markdown)


# ------------------------------------------------------------------ filtros --


def _roteiro_lista():
    """Lista de 23 itens com filtro por tipo e busca, como as páginas reais; alterna com uma
    'ficha' (o widget deixa de ser desenhado) para provar que o estado sobrevive à ida e volta."""
    import streamlit as st

    from src.ui.listas import barra_filtros, paginar, rodape_paginacao

    if st.session_state.get("visao") == "ficha":
        st.write("FICHA")
        st.stop()
    itens = [{"n": i, "tipo": "a" if i % 3 else "b", "nome": f"item {i}"} for i in range(23)]
    filtros = barra_filtros(
        "demo",
        [("todos", "Todos"), ("a", "Tipo A"), ("b", "Tipo B")],
        padrao="todos",
        contagens={"todos": 23, "a": 15, "b": 8},
        grupo="Tipo",
        busca="Buscar item",
    )
    visiveis = [
        i
        for i in itens
        if (filtros.valor == "todos" or i["tipo"] == filtros.valor) and filtros.busca.casefold() in i["nome"]
    ]
    filtros.resumo(len(visiveis), ("item", "itens"))
    pagina_atual, pagina = paginar("demo", visiveis)
    st.write("NUMEROS=" + ",".join(str(i["n"]) for i in pagina_atual))
    rodape_paginacao("demo", pagina)


def _numeros(app):
    achado = next(m.value for m in app.markdown if m.value.startswith("NUMEROS="))
    return [int(n) for n in achado.removeprefix("NUMEROS=").split(",") if n]


def _resumo(app):
    return re.sub(r"<[^>]+>", " ", next(m.value for m in app.markdown if "filtros-resumo" in m.value)).split()


def test_estado_inicial_mostra_total_sem_filtros_ativos():
    app = AppTest.from_function(_roteiro_lista).run()
    assert not app.exception
    assert app.pills[0].options == ["Todos · 23", "Tipo A · 15", "Tipo B · 8"]
    assert app.pills[0].value == "todos"
    assert _resumo(app) == ["23", "itens"]
    assert not [b for b in app.button if b.label == "Limpar filtros"]
    assert len(_numeros(app)) == 10


def test_pilula_nao_pode_ser_desmarcada():
    app = AppTest.from_function(_roteiro_lista).run()
    app.pills[0].set_value("a").run()
    assert app.pills[0].value == "a"
    assert app.pills[0].proto.required  # sem "nenhum filtro": sempre há um escolhido


def test_filtro_mostra_resultados_e_filtros_ativos():
    app = AppTest.from_function(_roteiro_lista).run()
    app.pills[0].set_value("b").run()
    assert _resumo(app)[:2] == ["8", "itens"]
    assert "Tipo: Tipo B" in _texto(app)
    assert [b.label for b in app.button if b.label == "Limpar filtros"] == ["Limpar filtros"]
    assert all(n % 3 == 0 for n in _numeros(app))


def test_busca_sem_resultado_informa_zero_e_o_termo():
    app = AppTest.from_function(_roteiro_lista).run()
    app.text_input(key="demo_busca").set_value("zzz").run()
    assert _resumo(app)[:2] == ["0", "itens"]
    assert "Busca: “zzz”" in _texto(app)
    assert _numeros(app) == []


def test_busca_e_escapada_no_resumo():
    app = AppTest.from_function(_roteiro_lista).run()
    app.text_input(key="demo_busca").set_value("<b>x</b>").run()
    assert "<b>x</b>" not in _texto(app)
    assert "&lt;b&gt;x&lt;/b&gt;" in _texto(app)


def test_limpar_filtros_em_uma_unica_acao():
    app = AppTest.from_function(_roteiro_lista).run()
    app.pills[0].set_value("b").run()
    app.text_input(key="demo_busca").set_value("item 3").run()
    app.button(key="demo_limpar").click().run()
    assert app.pills[0].value == "todos"
    assert app.text_input(key="demo_busca").value == ""
    assert _resumo(app) == ["23", "itens"]
    assert not [b for b in app.button if b.label == "Limpar filtros"]


def test_mudar_filtro_volta_para_a_primeira_pagina():
    app = AppTest.from_function(_roteiro_lista).run()
    app.button(key="demo_proxima").click().run()
    assert app.session_state["demo_pagina"] == 2
    app.pills[0].set_value("a").run()
    assert app.session_state["demo_pagina"] == 1


def test_busca_volta_para_a_primeira_pagina():
    app = AppTest.from_function(_roteiro_lista).run()
    app.button(key="demo_proxima").click().run()
    app.text_input(key="demo_busca").set_value("item").run()
    assert app.session_state["demo_pagina"] == 1


def test_estado_da_lista_sobrevive_a_abrir_e_fechar_uma_ficha():
    app = AppTest.from_function(_roteiro_lista).run()
    app.pills[0].set_value("a").run()
    app.text_input(key="demo_busca").set_value("item").run()
    app.button(key="demo_proxima").click().run()
    antes = _numeros(app)

    app.session_state["visao"] = "ficha"
    app.run()
    assert "FICHA" in _texto(app) and not list(app.pills)

    app.session_state["visao"] = "lista"
    app.run()
    assert app.pills[0].value == "a"
    assert app.text_input(key="demo_busca").value == "item"
    assert app.session_state["demo_pagina"] == 2
    assert _numeros(app) == antes


# ---------------------------------------------------------------- paginação --


def test_paginacao_anterior_informacao_e_proxima():
    app = AppTest.from_function(_roteiro_lista).run()
    assert "Mostrando 1 a 10 de 23 · página 1 de 3" in _texto(app)
    assert app.button(key="demo_anterior").disabled
    assert not app.button(key="demo_proxima").disabled
    assert [b.label for b in app.button if b.key in ("demo_anterior", "demo_proxima")] == ["Anterior", "Próxima"]

    app.button(key="demo_proxima").click().run()
    assert "Mostrando 11 a 20 de 23 · página 2 de 3" in _texto(app)
    app.button(key="demo_proxima").click().run()
    assert "Mostrando 21 a 23 de 23 · página 3 de 3" in _texto(app)
    assert app.button(key="demo_proxima").disabled
    app.button(key="demo_anterior").click().run()
    assert "página 2 de 3" in _texto(app)


def test_itens_por_pagina_reinicia_a_pagina():
    app = AppTest.from_function(_roteiro_lista).run()
    app.button(key="demo_proxima").click().run()
    app.selectbox(key="demo_por_pagina").set_value(25).run()
    assert app.session_state["demo_pagina"] == 1
    assert len(_numeros(app)) == 23
    assert "Mostrando 1 a 23 de 23 · página 1 de 1" in _texto(app)


def test_paginacao_nao_usa_number_input():
    app = AppTest.from_function(_roteiro_lista).run()
    assert not list(app.number_input)


def test_paginacao_some_quando_tudo_cabe_na_menor_pagina():
    def roteiro():
        from src.ui.listas import paginar, rodape_paginacao

        _, pagina = paginar("pequena", list(range(7)))
        rodape_paginacao("pequena", pagina)

    app = AppTest.from_function(roteiro).run()
    assert not app.exception and not list(app.button) and not list(app.selectbox)


def test_pagina_guardada_alem_do_fim_e_corrigida():
    def roteiro():
        import streamlit as st

        from src.ui.listas import paginar

        itens, pagina = paginar("curta", list(range(5)))
        st.write(f"pagina={pagina.pagina} itens={len(itens)}")

    app = AppTest.from_function(roteiro)
    app.session_state["curta_pagina"] = 9
    app.run()
    assert app.markdown[0].value == "pagina=1 itens=5"
    assert app.session_state["curta_pagina"] == 1


# --------------------------------------------------------------------- abas --


def _roteiro_abas():
    import streamlit as st

    from src.ui.listas import aba_ativa, abas

    total = st.session_state.get("total", 3)
    guias = abas("demo_abas", [f"Hoje · {total}", "Atrasadas", "Pagas"])
    for i, guia in enumerate(guias):
        with guia:
            if aba_ativa(guia):
                st.write(f"CONTEUDO {i}")


def _conteudos(app):
    return [m.value for m in app.markdown if m.value.startswith("CONTEUDO")]


def test_so_a_aba_ativa_executa_o_conteudo():
    app = AppTest.from_function(_roteiro_abas).run()
    assert not app.exception
    assert [t.label for t in app.tabs] == ["Hoje · 3", "Atrasadas", "Pagas"]
    assert _conteudos(app) == ["CONTEUDO 0"]


def test_aba_lembrada_vale_na_proxima_execucao():
    app = AppTest.from_function(_roteiro_abas)
    app.session_state["demo_abas_indice"] = 2
    app.run()
    assert _conteudos(app) == ["CONTEUDO 2"]


def test_aba_lembrada_continua_quando_o_rotulo_muda_de_contagem():
    """Registrar um pagamento muda o `· n` do rótulo; a aba não pode voltar para a primeira."""
    app = AppTest.from_function(_roteiro_abas)
    app.session_state["demo_abas_indice"] = 1
    app.run()
    app.session_state["total"] = 7
    app.run()
    assert [t.label for t in app.tabs][0] == "Hoje · 7"
    assert _conteudos(app) == ["CONTEUDO 1"]


def test_indice_de_aba_maior_que_o_numero_de_abas_e_limitado():
    app = AppTest.from_function(_roteiro_abas)
    app.session_state["demo_abas_indice"] = 9
    app.run()
    assert _conteudos(app) == ["CONTEUDO 2"]


def test_reiniciar_abas_esquece_a_aba():
    def roteiro():
        import streamlit as st

        from src.ui.listas import reiniciar_abas

        reiniciar_abas("x_abas")
        st.write("indice" in "".join(st.session_state))

    app = AppTest.from_function(roteiro)
    app.session_state["x_abas_indice"] = 3
    app.run()
    assert "x_abas_indice" not in app.session_state


# -------------------------------------------------- padrão único nas páginas --

_PAGINAS_DE_LISTA = ["motos", "clientes", "contratos", "documentos", "manutencao", "vistorias"]


def test_listas_usam_a_barra_de_filtros_e_a_paginacao_padrao():
    for nome in _PAGINAS_DE_LISTA:
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "barra_filtros(" in codigo, nome
        assert "rodape_paginacao(" in codigo or nome == "manutencao", nome  # Manutenção: aba Histórico
        assert "_pills(" not in codigo and "_rodape_paginacao" not in codigo, nome
        assert "key=f\"pill_" not in codigo and 'key="pill_' not in codigo, nome


def test_nenhuma_pagina_monta_abas_ou_paginacao_na_mao():
    for arquivo in sorted(UI.glob("*.py")):
        if arquivo.name == "listas.py":
            continue
        codigo = arquivo.read_text(encoding="utf-8")
        assert "st.tabs(" not in codigo, f"{arquivo.name}: use `abas` de src/ui/listas.py"
        assert '"Página"' not in codigo, f"{arquivo.name}: paginação por number_input"


def test_a_pagina_de_relatorios_tambem_usa_o_seletor_padrao():
    codigo = (UI / "relatorios.py").read_text(encoding="utf-8")
    assert "barra_filtros(" in codigo and "abas(" in codigo


def test_navegacao_agrupada_por_area_sem_mudar_as_rotas():
    app = (RAIZ / "app.py").read_text(encoding="utf-8")
    grupos = re.findall(r'^    "([^"]+)": \[', app, flags=re.M)
    assert grupos == ["Operação", "Cadastros", "Frota", "Gestão", "Sistema"]
    arquivos = re.findall(r'st\.Page\("(pages/[^"]+)"', app)
    # o portal do locatário tem menu próprio (ARQUIVO_PORTAL); as demais páginas estão todas nos grupos
    esperado = {f"pages/{p.name}" for p in (RAIZ / "pages").glob("*.py")} - {"pages/11_Portal_Locatario.py"}
    assert sorted(arquivos) == sorted(esperado)
