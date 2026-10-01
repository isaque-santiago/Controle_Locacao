"""Listas e tabelas resilientes (Plano de melhorias, Etapa 4): cartões com estrutura explícita,
tabelas semânticas e ausência de CSS dependente da posição das colunas."""

import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.ui.registros import campo, html_dados, html_identidade
from tests.test_manutencao_ui import HISTORICO
from tests.test_telas_dados import abrir, servicos  # noqa: F401  (fixture)

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"


def _texto(app):
    return " ".join(m.value for m in app.markdown)


def _pares(html):
    """Pares (rótulo, valor) na ordem em que aparecem no HTML dos dados."""
    return re.findall(r'<dt class="registro__rotulo">(.*?)</dt><dd class="registro__valor">(.*?)</dd>', html)


# ------------------------------------------------------------ componente --


def test_rotulo_acompanha_o_valor_mesmo_trocando_a_ordem_dos_campos():
    a, b = campo("Vencimento", "01/01/2027"), campo("Valor", "R$ 10,00")
    assert _pares(html_dados([a, b])) == [("Vencimento", "01/01/2027"), ("Valor", "R$ 10,00")]
    assert _pares(html_dados([b, a])) == [("Valor", "R$ 10,00"), ("Vencimento", "01/01/2027")]


def test_dados_sao_lista_de_definicoes_com_rotulo_escapado():
    html = html_dados([campo("A <b>", "x")])
    assert html.startswith('<dl class="registro__dados">')
    assert "A &lt;b&gt;" in html and "<b>" not in html


def test_identidade_leva_titulo_subtitulo_e_selo_em_classes_proprias():
    html = html_identidade("TITULO", selo="SELO", subtitulo="SUB")
    assert 'class="registro__titulo">TITULO<' in html
    assert 'class="registro__subtitulo">SUB<' in html
    assert 'class="registro__selo">SELO<' in html
    assert "registro__selo" not in html_identidade("T")


def _roteiro_registros():
    import streamlit as st

    from src.ui.componentes import botao_acao
    from src.ui.registros import campo, lista_registros, registro

    with lista_registros("demo", acoes=2):
        for i in ("a", "b"):
            with registro("demo", i, f"Item {i}", [campo("Valor", "1")], selo="ok", acoes=i == "a") as acoes:
                if i == "a":
                    if botao_acao(acoes, "editar", f"editar_{i}"):
                        st.write("EDITOU")
                    botao_acao(acoes, "abrir", f"abrir_{i}")
        with registro("demo", "c", "Item c", [], estado="selecionado", acoes=False):
            pass


def test_registro_expoe_acoes_com_texto_e_chaves_estaveis():
    app = AppTest.from_function(_roteiro_registros).run()
    assert not app.exception
    assert {b.key: b.label for b in app.button} == {"editar_a": "Editar", "abrir_a": "Abrir"}
    app.button(key="editar_a").click().run()
    assert "EDITOU" in _texto(app)


def test_registro_sem_campos_nao_desenha_lista_de_dados():
    app = AppTest.from_function(_roteiro_registros).run()
    corpos = [m.value for m in app.markdown if "registro__id" in m.value]
    assert len(corpos) == 3
    assert sum("registro__dados" in m.value for m in app.markdown) == 2  # o registro "c" não tem dados


# ---------------------------------------------------------- tabela somente leitura --


def _roteiro_tabela():
    from src.ui.componentes import tabela_html

    tabela_html(["Data", "Valor", ""], [["01/01/2027", "R$ 1,00", "<i>barra</i>"]], legenda="Resumo de teste")


def test_tabela_somente_leitura_tem_semantica_de_tabela():
    app = AppTest.from_function(_roteiro_tabela).run()
    html = next(m.value for m in app.markdown if "tabela-leitura" in m.value)
    assert '<table role="table" aria-label="Resumo de teste">' in html
    assert '<caption class="so-leitor">Resumo de teste</caption>' in html
    assert html.count('scope="col"') == 2  # Data e Valor; a coluna decorativa fica de fora
    assert 'role="columnheader" scope="col">Data</th>' in html
    assert 'role="cell" data-label="Valor">R$ 1,00</td>' in html
    assert '<th role="columnheader" aria-hidden="true">' in html  # barra de proporção: decorativa
    assert 'role="row"' in html and 'role="rowgroup"' in html


def test_tabela_vazia_mostra_o_estado_vazio_em_uma_linha():
    def roteiro():
        from src.ui.componentes import tabela_html

        tabela_html(["A", "B"], [])

    app = AppTest.from_function(roteiro).run()
    html = next(m.value for m in app.markdown if "tabela-leitura" in m.value)
    assert 'colspan="2"' in html and "Nenhum registro encontrado." in html


def test_toda_tabela_somente_leitura_tem_nome_para_leitor_de_tela():
    for arquivo in sorted(UI.glob("*.py")):
        codigo = arquivo.read_text(encoding="utf-8")
        chamadas = len(re.findall(r"\btabela_html\(", codigo)) - len(re.findall(r"def tabela_html\(", codigo))
        if arquivo.name != "componentes.py":
            assert codigo.count("legenda=") >= chamadas, f"{arquivo.name}: tabela_html sem `legenda`"


# ------------------------------------------------------------------ páginas --


def test_documentos_renderiza_cartoes_com_rotulos_e_acoes_visiveis(servicos):
    app = abrir("7_Documentos.py")
    assert not app.exception and not app.error
    html = _texto(app)
    assert 'class="registro__id"' in html and 'class="registro__dados"' in html
    for rotulo in ("Tipo", "Referência", "Vencimento", "Valor"):
        assert f'<dt class="registro__rotulo">{rotulo}</dt>' in html
    rotulos = {b.key: b.label for b in app.button if b.key and b.key.endswith("_d")}
    assert rotulos == {"comprovante_doc_d": "Comprovante", "editar_doc_d": "Editar", "regularizar_doc_d": "Regularizar"}


def test_historico_de_manutencao_escapa_a_descricao(servicos):
    servicos["manutencao.listar_manutencoes"].return_value = [{**HISTORICO[0], "descricao": "<script>x</script>"}]
    app = abrir("6_Manutencao.py", manutencao_abas_indice=1)
    html = _texto(app)
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html


def test_catalogo_mostra_situacao_em_texto_e_nao_so_interruptor(servicos):
    app = abrir("6_Manutencao.py", manutencao_abas_indice=2)
    html = _texto(app)
    assert "badge" in html and ">Ativo<" in html


# ---------------------------------------------------- peças e serviços (repetidor) --


def _abrir_dialogo_registrar():
    # Dentro de st.dialog os cliques reexecutam só o fragmento; o AppTest reexecuta o script
    # todo, então o diálogo é aberto direto (mesmo padrão de test_documentos_ui).
    def roteiro():
        from src.ui.manutencao import _dialog_registrar

        _dialog_registrar()

    return AppTest.from_function(roteiro, default_timeout=20).run()


def test_pecas_e_servicos_adicionais_usam_campos_e_nao_tabela_em_canvas(servicos):
    app = _abrir_dialogo_registrar()
    assert not app.exception and not app.error
    assert not list(app.get("arrow_data_frame"))
    assert [b.label for b in app.button if b.label == "Adicionar peça ou serviço"]

    app.button(key="manreg_extra_adicionar").click().run()
    assert not app.exception and not app.error
    rotulos = [e.label for e in app.text_input if e.key and e.key.startswith("manreg_extra_")]
    assert rotulos == ["Descrição", "Quantidade", "Valor unitário (R$)"]
    assert [b.label for b in app.button if b.key == "manreg_extra_remover_0"] == ["Remover"]


def test_pecas_adicionais_entram_na_previa_e_podem_ser_removidas(servicos):
    app = _abrir_dialogo_registrar()
    app.button(key="manreg_extra_adicionar").click().run()
    app.text_input(key="manreg_extra_desc_0").set_value("Pastilha")
    app.text_input(key="manreg_extra_qtd_0").set_value("2")
    app.text_input(key="manreg_extra_valor_0").set_value("15,50").run()
    assert "R$ 31,00" in _texto(app)  # 2 × 15,50 no custo de peças

    app.button(key="manreg_extra_remover_0").click().run()
    assert not [e for e in app.text_input if e.key and e.key.startswith("manreg_extra_desc_")]
    assert "R$ 31,00" not in _texto(app)


def test_salvar_envia_as_pecas_adicionais_validadas(servicos):
    with patch("src.services.manutencao.registrar_manutencao") as registrar:
        app = _abrir_dialogo_registrar()
        app.text_area(key="manreg_descricao").set_value("Freios")
        app.button(key="manreg_extra_adicionar").click().run()
        app.text_input(key="manreg_extra_desc_0").set_value("Pastilha")
        app.text_input(key="manreg_extra_qtd_0").set_value("2")
        app.text_input(key="manreg_extra_valor_0").set_value("15,50").run()
        app.button(key="manreg_salvar").click().run()
    assert not app.error, [e.value for e in app.error]
    itens = registrar.call_args.kwargs["itens"]
    assert [(i["descricao"], i["quantidade"], i["valor_unitario"]) for i in itens] == [
        ("Pastilha", Decimal("2"), Decimal("15.50"))
    ]


# ------------------------------------------------- CSS e código sem posição de coluna --


def test_css_sem_regras_posicionais_de_colunas_do_streamlit():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    for linha in css.splitlines():
        assert not ("stColumn" in linha and "nth-child" in linha), linha[:120]
    assert "_card_" not in css.replace("dashboard_card_hoje", "")
    assert "grid-area: act" not in css


def test_paginas_nao_montam_linhas_de_lista_com_colunas():
    paginas = ["motos", "clientes", "contratos", "documentos", "manutencao", "vistorias", "cobrancas", "dashboard"]
    for nome in paginas:
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "_cabecalho_tabela(st.columns" not in codigo, nome
        assert "_card_lista" not in codigo and 'key="cobrancas_card' not in codigo, nome
        assert "lista_registros(" in codigo, f"{nome}: lista interativa deve usar src/ui/registros.py"


def test_nao_ha_tabela_em_canvas_no_app():
    for arquivo in sorted(UI.glob("*.py")):
        codigo = arquivo.read_text(encoding="utf-8")
        assert "st.dataframe" not in codigo and "st.data_editor" not in codigo, arquivo.name


def test_acoes_de_lista_nao_escondem_o_texto_no_css():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    bloco = css[css.index("REGISTROS —") : css.index("   RESPONSIVE")]
    assert "clip-path" not in bloco.split("/* Ações:")[1].split("@container")[0]
