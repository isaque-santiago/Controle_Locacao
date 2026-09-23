"""Tela de Vistorias: lista, filtros, registro em modal e comparação."""

from datetime import date
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

from src.domain.valores import hoje_br
from tests.test_telas_dados import abrir, servicos  # noqa: F401  (fixture)

ENTREGA = {
    "id": "v1", "contrato_id": "ct", "moto_id": "m", "tipo": "entrega", "km": 100,
    "data": "2026-09-01T10:00:00+00:00", "nivel_combustivel": "cheio",
    "checklist": {"retrovisores": "ok", "buzina": "ok"}, "avarias": None, "fotos": [],
}
DEVOLUCAO = {
    "id": "v2", "contrato_id": "ct", "moto_id": "m", "tipo": "devolucao", "km": 2620,
    "data": "2026-09-20T10:00:00+00:00", "nivel_combustivel": "1/2",
    "checklist": {"retrovisores": "avaria", "buzina": "ok"},
    "avarias": "Retrovisor direito trincado", "fotos": [],
}


def _texto(app):
    return " ".join(m.value for m in app.markdown)


def test_lista_mostra_cabecalho_colunas_e_linhas(servicos):
    servicos["vistorias.listar"].return_value = [DEVOLUCAO, ENTREGA]
    app = abrir("8_Vistorias.py")
    assert not app.exception and not app.error
    texto = _texto(app)
    assert "Entregas e devoluções registradas" in texto
    for coluna in ("Data", "Contrato", "Tipo", "Km", "Combustível", "Avarias"):
        assert coluna in texto
    assert "Pessoa teste" in texto and "ABC-1D23" in texto
    assert "Retrovisor direito trincado" in texto
    assert "2.620 km" in texto
    assert texto.index("20/09/2026") < texto.index("01/09/2026")  # mais recente primeiro


def test_filtro_por_tipo_e_contagens(servicos):
    servicos["vistorias.listar"].return_value = [DEVOLUCAO, ENTREGA]
    app = abrir("8_Vistorias.py")
    rotulos = [b.label for b in app.button]
    assert {"Todas · 2", "Entrega · 1", "Devolução · 1"} <= set(rotulos)

    next(b for b in app.button if b.label == "Devolução · 1").click().run()
    texto = _texto(app)
    assert "Retrovisor direito trincado" in texto
    assert "01/09/2026" not in texto


def test_busca_por_cliente_ou_placa(servicos):
    servicos["vistorias.listar"].return_value = [ENTREGA]
    app = abrir("8_Vistorias.py")
    next(t for t in app.text_input if t.key == "vistorias_busca").set_value("zzz").run()
    assert "Nenhuma vistoria encontrada." in _texto(app)
    next(t for t in app.text_input if t.key == "vistorias_busca").set_value("abc1d").run()
    assert "Nenhuma vistoria encontrada." not in _texto(app)


def test_lista_vazia(servicos):
    servicos["vistorias.listar"].return_value = []
    app = abrir("8_Vistorias.py")
    assert not app.exception and not app.error
    assert "Nenhuma vistoria encontrada." in _texto(app)


def test_seta_abre_a_comparacao_do_contrato(servicos):
    servicos["vistorias.listar"].return_value = [ENTREGA]
    servicos["vistorias.comparar_entrega_devolucao"].return_value = {
        "entrega": ENTREGA,
        "devolucao": DEVOLUCAO,
        "diferencas": {"retrovisores": {"entrega": "ok", "devolucao": "avaria"}},
    }
    app = abrir("8_Vistorias.py")
    next(b for b in app.button if b.key == "ver_vist_v1").click().run()
    assert not app.exception and not app.error
    texto = _texto(app)
    assert "Pessoa teste → Honda CG" in texto
    assert "2.520 km" in texto  # km rodados
    assert "1 registrada(s)" in texto
    assert "Retrovisor direito trincado" in texto
    assert "Retrovisores" in texto and "Avaria" in texto
    assert any("fundo amarelo mudaram" in c.value for c in app.caption)
    assert any(b.label == "‹ Vistorias" for b in app.button)


def test_comparacao_sem_devolucao_mostra_pendente(servicos):
    servicos["vistorias.comparar_entrega_devolucao"].return_value = {
        "entrega": ENTREGA, "devolucao": None, "diferencas": None,
    }
    app = abrir("8_Vistorias.py")
    app.session_state["vistorias_visao"] = "comparacao"
    app.session_state["vistorias_contrato"] = "ct"
    app.run()
    assert not app.exception and not app.error
    assert "será registrada no encerramento do contrato" in _texto(app)


def test_voltar_retorna_para_a_lista(servicos):
    app = abrir("8_Vistorias.py")
    app.session_state["vistorias_visao"] = "comparacao"
    app.session_state["vistorias_contrato"] = "ct"
    app.run()
    next(b for b in app.button if b.label == "‹ Vistorias").click().run()
    assert "Entregas e devoluções registradas" in _texto(app)


def test_dialogo_registrar_oferece_so_tipos_faltantes(servicos):
    servicos["vistorias.listar"].return_value = [ENTREGA]
    app = abrir("8_Vistorias.py")
    next(b for b in app.button if b.label == "+ Registrar vistoria").click().run()
    assert not app.exception and not app.error
    assert any(b.label == "Salvar vistoria" for b in app.button)
    tipo = next(r for r in app.radio if r.label == "Tipo")
    assert tipo.options == ["Devolução"]


def test_dialogo_sem_contratos_pendentes_avisa(servicos):
    servicos["vistorias.listar"].return_value = [ENTREGA, DEVOLUCAO]
    app = abrir("8_Vistorias.py")
    next(b for b in app.button if b.label == "+ Registrar vistoria").click().run()
    assert any("já têm vistoria" in i.value for i in app.info)


def _abrir_dialogo_registro():
    def roteiro():
        from src.ui.vistorias import _dialog_registrar

        contrato = {
            "id": "ct", "moto_id": "m", "cliente_id": "cl",
            "data_inicio": "2026-09-01", "status": "ativo",
        }
        moto = {"id": "m", "placa": "ABC1D23", "marca": "Honda", "modelo": "CG", "km_atual": 100}
        _dialog_registrar([(contrato, ["devolucao"])], {"m": moto}, {"cl": "Pessoa teste"})

    return AppTest.from_function(roteiro, default_timeout=20).run()


def test_salvar_registra_com_dados_do_formulario():
    with patch(
        "src.services.vistorias.registrar_vistoria", return_value={"vistoria_id": "novo"}
    ) as registrar:
        app = _abrir_dialogo_registro()
        next(r for r in app.radio if r.label == "Nível de combustível").set_value("3/4")
        next(s for s in app.selectbox if s.label == "Buzina").set_value("avaria")
        next(t for t in app.text_area if t.label == "Avarias (se houver)").set_value(" Risco ")
        next(b for b in app.button if b.label == "Salvar vistoria").click().run()

    assert not app.exception and not app.error, [e.value for e in app.error]
    args, kwargs = registrar.call_args
    assert args == ("ct", "m", "devolucao")
    assert kwargs["km"] == 100
    assert kwargs["nivel_combustivel"] == "3/4"
    assert kwargs["avarias"] == "Risco"
    assert kwargs["checklist"]["buzina"] == "avaria"
    assert kwargs["checklist"]["farol_dianteiro"] == "ok"
    assert kwargs["data"].tzinfo is not None
    assert kwargs["data"].astimezone(ZoneInfo("America/Sao_Paulo")).date() == hoje_br()
    assert app.session_state["mensagem_sucesso"] == "Vistoria registrada."


def test_itens_adicionais_entram_no_checklist():
    with patch("src.services.vistorias.registrar_vistoria", return_value={}) as registrar:
        app = _abrir_dialogo_registro()
        next(t for t in app.text_area if t.label.startswith("Um por linha")).set_value(
            "kit ferramentas=ausente"
        )
        next(b for b in app.button if b.label == "Salvar vistoria").click().run()

    assert registrar.call_args.kwargs["checklist"]["kit ferramentas"] == "ausente"


def test_itens_adicionais_invalidos_mostram_erro_sem_gravar():
    with patch("src.services.vistorias.registrar_vistoria") as registrar:
        app = _abrir_dialogo_registro()
        next(t for t in app.text_area if t.label.startswith("Um por linha")).set_value("sem_estado")
        next(b for b in app.button if b.label == "Salvar vistoria").click().run()

    registrar.assert_not_called()
    assert any("nome=estado" in e.value for e in app.error)


def test_salvar_recusa_data_anterior_ao_inicio_do_contrato():
    with patch("src.services.vistorias.registrar_vistoria") as registrar:
        app = _abrir_dialogo_registro()
        next(d for d in app.date_input if d.label == "Data").set_value(date(2026, 8, 1))
        next(b for b in app.button if b.label == "Salvar vistoria").click().run()

    registrar.assert_not_called()
    assert any("anteceder o início do contrato" in e.value for e in app.error)


def test_falha_no_envio_de_foto_nao_desfaz_a_vistoria():
    from src.ui.vistorias import _enviar_fotos, _mensagem_fotos

    foto = MagicMock()
    foto.name, foto.type = "a.jpg", "image/jpeg"
    foto.getvalue.return_value = b"x"
    with patch("src.services.vistorias.anexar_foto", side_effect=RuntimeError("storage fora")):
        falhas = _enviar_fotos({"vistoria_id": "novo"}, [foto, foto])
    assert falhas == 2
    assert "2 foto(s) não foram enviadas" in _mensagem_fotos("Vistoria registrada.", falhas)
    assert _mensagem_fotos("Vistoria registrada.", 0) == "Vistoria registrada."
