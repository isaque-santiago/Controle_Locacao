"""Tela de Documentos: lista da frota, filtros e diálogos de cadastro e regularização."""

from datetime import date
from decimal import Decimal
from time import time
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from tests.test_telas_dados import DOCUMENTO, RAIZ, abrir, servicos  # noqa: F401  (fixture)

VENCIDO = {**DOCUMENTO, "id": "d1", "vencimento": "2020-01-31"}
EM_DIA = {
    **DOCUMENTO,
    "id": "d2",
    "tipo": "seguro",
    "descricao": "apólice 445871",
    "vencimento": "2999-01-01",
    "valor": Decimal("680.00"),
}
REGULARIZADO = {**DOCUMENTO, "id": "d3", "vencimento": "2020-02-01", "regularizado": True}


def _texto(app):
    return " ".join(m.value for m in app.markdown)


def test_cabecalho_contagens_e_situacoes(servicos):
    servicos["documentos.listar_todos"].return_value = [EM_DIA, REGULARIZADO, VENCIDO]
    app = abrir("7_Documentos.py")
    assert not app.exception
    texto = _texto(app)
    assert "1 vencido(s) · 0 a vencer" in texto
    assert "Regularizado" in texto and "Vencido" in texto and "Em dia" in texto
    assert "apólice 445871" in texto
    rotulos = [b.label for b in app.button]
    assert {"Todos · 3", "Vencido · 1", "A vencer · 0", "Em dia · 2"} <= set(rotulos)


def test_filtro_vencido_mostra_so_vencidos(servicos):
    servicos["documentos.listar_todos"].return_value = [EM_DIA, VENCIDO]
    app = abrir("7_Documentos.py")
    next(b for b in app.button if b.label.startswith("Vencido")).click().run()
    texto = _texto(app)
    assert "31/01/2020" in texto
    assert "01/01/2999" not in texto


def test_regularizar_so_para_documento_pendente(servicos):
    servicos["documentos.listar_todos"].return_value = [VENCIDO, REGULARIZADO]
    app = abrir("7_Documentos.py")
    chaves = {b.key for b in app.button}
    assert "regularizar_doc_d1" in chaves
    assert "regularizar_doc_d3" not in chaves


def _abrir_dialogo(roteiro):
    # O envio de formulário dentro de st.dialog reexecuta só o fragmento; o
    # AppTest reexecuta o script todo, então o diálogo é aberto direto.
    return AppTest.from_function(roteiro, default_timeout=20).run()


def _roteiro_novo():
    from src.ui.documentos import _dialog_novo

    _dialog_novo({})


def _roteiro_regularizar():
    from src.ui.documentos import _dialog_regularizar

    _dialog_regularizar(
        {
            "id": "d1",
            "moto_id": "m",
            "tipo": "ipva",
            "ano_referencia": 2026,
            "vencimento": "2026-01-31",
            "regularizado": False,
        },
        {"placa": "ABC1D23"},
    )


def test_botao_novo_documento_abre_dialogo(servicos):
    app = abrir("7_Documentos.py")
    next(b for b in app.button if b.label == "+ Novo documento").click().run()
    assert not app.error
    assert any(b.label == "Salvar documento" for b in app.button)
    assert any(e.label == "Valor (R$)" for e in app.text_input)


def test_salvar_novo_documento_envia_dados(servicos):
    with patch("src.services.documentos.criar", return_value={"id": "novo"}) as criar:
        app = _abrir_dialogo(_roteiro_novo)
        next(e for e in app.text_input if e.label == "Valor (R$)").set_value("420,00")
        next(d for d in app.date_input if d.label == "Vencimento").set_value(date(2027, 1, 31))
        next(b for b in app.button if b.label == "Salvar documento").click().run()
    assert not app.error, [e.value for e in app.error]
    dados = criar.call_args.args[0]
    assert dados["vencimento"] == "2027-01-31"
    assert dados["valor"] == "420.00"
    assert dados["moto_id"] == "m"


def test_salvar_sem_vencimento_mostra_erro(servicos):
    app = _abrir_dialogo(_roteiro_novo)
    next(b for b in app.button if b.label == "Salvar documento").click().run()
    assert any("vencimento" in e.value for e in app.error)


def test_regularizar_guarda_sugestao_do_ano_seguinte(servicos):
    sugestao = {"tipo": "ipva", "ano_referencia": 2027, "vencimento": None, "regularizado": False}
    with patch(
        "src.services.documentos.regularizar",
        return_value={"documento": {}, "sugestao_proximo": sugestao},
    ) as regularizar:
        app = _abrir_dialogo(_roteiro_regularizar)
        assert any("2027" in c.label for c in app.checkbox)
        next(b for b in app.button if b.label == "Confirmar").click().run()
    regularizar.assert_called_once()
    assert app.session_state["documentos_sugestao"] == {**sugestao, "moto_id": "m"}


def test_regularizar_sem_marcar_proximo_nao_guarda_sugestao(servicos):
    with patch(
        "src.services.documentos.regularizar",
        return_value={"documento": {}, "sugestao_proximo": {"ano_referencia": 2027}},
    ):
        app = _abrir_dialogo(_roteiro_regularizar)
        next(c for c in app.checkbox if "2027" in c.label).uncheck()
        next(b for b in app.button if b.label == "Confirmar").click().run()
    assert "documentos_sugestao" not in app.session_state


def test_sugestao_pendente_reabre_cadastro_na_pagina(servicos):
    app = AppTest.from_file(str(RAIZ / "pages" / "7_Documentos.py"), default_timeout=20)
    app.session_state["usuario"] = {"id": "teste", "email": "teste@example.com"}
    app.session_state["ultima_atividade"] = time()
    app.session_state["documentos_sugestao"] = {
        "tipo": "seguro", "ano_referencia": 2027, "vencimento": None, "moto_id": "m",
    }
    app.run()
    assert not app.error
    assert any(n.value == 2027 for n in app.number_input)
