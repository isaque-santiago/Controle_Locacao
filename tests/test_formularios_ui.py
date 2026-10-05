"""Formulários e fluxos transacionais (Plano de melhorias, Etapa 5): campos tipados, rodapé,
confirmação de ações destrutivas e assistente de contrato que não perde o progresso."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from tests.test_manutencao_ui import HISTORICO
from tests.test_telas_dados import CLIENTE, COBRANCA, CONTRATO, MOTO, abrir, servicos  # noqa: F401  (fixture)

UI = Path(__file__).resolve().parents[1] / "src" / "ui"
CHAVES_WIZARD = {"contratos_visao": "wizard", "contrato_cliente_id": "cl", "contrato_moto_id": "m"}


def _texto(app):
    return " ".join(m.value for m in app.markdown)


def _roteiro(funcao, default_timeout=20):
    return AppTest.from_function(funcao, default_timeout=default_timeout).run()


# ------------------------------------------------------------------ rodapé --


def _roteiro_rodape():
    import streamlit as st

    from src.ui.formularios import rodape_formulario

    acao = rodape_formulario(
        "Salvar tudo",
        "demo",
        desabilitado=st.session_state.get("travar", True),
        motivo="Descrição: informe o serviço.",
    )
    st.session_state["resultado"] = (acao.confirmou, acao.cancelou)


def test_rodape_coloca_cancelar_antes_da_acao_principal_e_explica_o_bloqueio():
    app = _roteiro(_roteiro_rodape)
    assert [b.key for b in app.button] == ["demo_cancelar", "demo_salvar"]
    assert [b.label for b in app.button] == ["Cancelar", "Salvar tudo"]
    assert app.button(key="demo_salvar").disabled
    assert "Descrição: informe o serviço." in _texto(app)
    assert 'role="status"' in _texto(app)


def test_rodape_libera_a_confirmacao_e_some_com_o_motivo():
    app = _roteiro(_roteiro_rodape)
    app.session_state["travar"] = False
    app.run()
    assert not app.button(key="demo_salvar").disabled
    assert "Descrição: informe o serviço." not in _texto(app)
    app.button(key="demo_salvar").click().run()
    assert app.session_state["resultado"] == (True, False)


def _roteiro_rodape_perigo():
    from src.ui.formularios import rodape_formulario

    rodape_formulario("Apagar", "risco", perigo=True, cancelar="Manter")


def test_rodape_de_acao_destrutiva_usa_chave_de_perigo_e_cancelar_personalizado():
    app = _roteiro(_roteiro_rodape_perigo)
    assert [b.key for b in app.button] == ["risco_cancelar", "perigo_risco_confirmar"]
    assert app.button(key="risco_cancelar").label == "Manter"


# ------------------------------------------------------------------ campos --


def _roteiro_campos():
    import streamlit as st

    from src.ui.formularios import campo_cpf, campo_inteiro, campo_moeda, campo_percentual, campo_placa, campo_telefone

    st.session_state["lido"] = {
        "moeda": campo_moeda("Valor", "1234.5", "k_moeda", obrigatorio=True),
        "pct": campo_percentual("Multa", 2, "k_pct"),
        "dias": campo_inteiro("Carência", 5, "k_dias", sufixo="dias"),
        "cpf": campo_cpf("CPF", "52998224725", "k_cpf"),
        "tel": campo_telefone("Telefone", "11912345678", "k_tel"),
        "placa": campo_placa("Placa", "abc1d23", "k_placa"),
    }


def test_campos_mostram_o_valor_inicial_no_padrao_brasileiro():
    app = _roteiro(_roteiro_campos)
    assert not app.exception
    assert app.session_state["lido"] == {
        "moeda": "1.234,50",
        "pct": "2,00",
        "dias": 5,
        "cpf": "529.982.247-25",
        "tel": "(11) 91234-5678",
        "placa": "ABC-1D23",
    }
    assert app.text_input(key="k_moeda").label == "Valor *"


def test_campos_declaram_prefixo_sufixo_e_regra_do_navegador():
    app = _roteiro(_roteiro_campos)
    html = _texto(app)  # nenhum HTML de prefixo: o prefixo e o sufixo vêm do CSS pela chave do container
    assert "R$" not in html
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    for chave in ("st-key-moeda_", "st-key-sfx_pct_", "st-key-sfx_km_", "st-key-sfx_dias_"):
        assert chave in css
    from streamlit.proto.TextInput_pb2 import TextInput

    for chave in ("k_cpf", "k_tel"):
        proto = app.text_input(key=chave).proto
        assert proto.type == TextInput.PHONE  # teclado numérico no celular
        assert proto.validate_regex and proto.validate_message  # erro ao lado do campo, no navegador
    assert app.text_input(key="k_placa").proto.validate_regex
    assert app.text_input(key="k_moeda").proto.validate_message.startswith("Valor:")


# ------------------------------------------------------------------ assistente --


def test_indicador_de_etapas_marca_a_etapa_atual_e_as_concluidas():
    def roteiro():
        from src.ui.componentes import indicador_etapas

        indicador_etapas(3, ["Cliente", "Moto", "Condições", "Confirmar"], nome="Etapas do teste")

    app = _roteiro(roteiro)
    html = _texto(app)
    assert html.count("<li ") == 4
    assert html.count('aria-current="step"') == 1
    assert "etapa--atual" in html and html.count("(concluída)") == 2
    assert '<ol class="etapas__lista">' in html and 'aria-label="Etapas do teste"' in html
    assert "Etapa 3 de 4: Condições" in html


def test_assistente_etapa_1_desabilita_avancar_e_diz_o_motivo(servicos):
    app = abrir("4_Contratos.py", contratos_visao="wizard", contrato_etapa=1)
    assert not app.exception
    assert app.button(key="wiz1_salvar").disabled
    assert "Selecione um cliente para continuar." in _texto(app)
    assert [b.label for b in app.button if b.key in ("wiz1_cancelar", "wiz1_salvar")] == ["Cancelar", "Avançar"]


def test_assistente_etapa_2_exige_moto(servicos):
    app = abrir("4_Contratos.py", contratos_visao="wizard", contrato_etapa=2, contrato_cliente_id="cl")
    assert not app.exception
    assert app.button(key="wiz2_salvar").disabled
    assert "Selecione uma moto disponível para continuar." in _texto(app)
    app.button(key="sel_moto_card_m").click().run()
    assert not app.button(key="wiz2_salvar").disabled
    assert [b.label for b in app.button if b.key in ("wiz2_cancelar", "wiz2_salvar")] == ["Voltar", "Avançar"]


def test_assistente_etapa_3_bloqueia_valor_invalido_e_nomeia_o_campo(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    assert not app.exception and not app.error
    # a moto do exemplo não tem valor sugerido: o valor do período começa em 0,00 e o assistente explica
    assert app.button(key="wiz3_salvar").disabled
    assert "Valor do período: informe um valor maior que zero." in _texto(app)
    app.text_input(key="wiz_valor").set_value("12,345").run()
    assert app.button(key="wiz3_salvar").disabled
    assert "Valor do período: use no máximo duas casas decimais" in _texto(app)
    app.text_input(key="wiz_valor").set_value("1.200,00").run()
    assert not app.button(key="wiz3_salvar").disabled


def test_assistente_etapa_3_recusa_fim_antes_do_inicio(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    app.text_input(key="wiz_valor").set_value("900,00")
    app.date_input(key="wiz_inicio").set_value(date(2026, 12, 10))
    app.checkbox(key="wiz_indeterminado").uncheck().run()
    app.date_input(key="wiz_fim").set_value(date(2026, 12, 1)).run()
    assert app.button(key="wiz3_salvar").disabled
    assert "Fim previsto: escolha uma data igual ou posterior ao início." in _texto(app)


def test_assistente_etapa_3_comeca_semanal_e_por_prazo_indeterminado(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    assert app.radio(key="wiz_periodicidade").value == "semanal"
    assert app.checkbox(key="wiz_indeterminado").value is True
    assert not [d for d in app.date_input if d.key == "wiz_fim"]


def test_assistente_etapa_3_indeterminado_avanca_sem_data_final(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    app.text_input(key="wiz_valor").set_value("900,00").run()
    assert not app.button(key="wiz3_salvar").disabled
    app.button(key="wiz3_salvar").click().run()
    assert app.session_state["contrato_etapa"] == 4
    assert app.session_state["contrato_condicoes"]["data_fim_prevista"] is None
    assert "Indeterminado" in _texto(app)
    assert any("primeiros 30 dias" in c.value for c in app.caption)


def test_assistente_etapa_3_com_prazo_definido_envia_a_data_final(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    app.text_input(key="wiz_valor").set_value("900,00")
    app.date_input(key="wiz_inicio").set_value(date(2026, 12, 1))
    app.checkbox(key="wiz_indeterminado").uncheck().run()
    app.date_input(key="wiz_fim").set_value(date(2026, 12, 29)).run()
    app.button(key="wiz3_salvar").click().run()
    assert app.session_state["contrato_condicoes"]["data_fim_prevista"] == "2026-12-29"
    assert not any("primeiros 30 dias" in c.value for c in app.caption)


def test_voltar_e_alterar_nao_perdem_o_que_foi_preenchido(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    app.text_input(key="wiz_valor").set_value("950,00")
    app.text_input(key="wiz_caucao").set_value("100,00")
    app.radio(key="wiz_periodicidade").set_value("quinzenal").run()

    app.button(key="alterar_moto_3").click().run()  # volta à etapa 2
    assert app.session_state["contrato_etapa"] == 2
    assert app.session_state["contrato_cliente_id"] == "cl"
    assert app.session_state["contrato_moto_id"] == "m"
    assert app.session_state["contrato_rascunho"]["valor_periodo"] == "950,00"

    app.button(key="wiz2_salvar").click().run()  # avança de novo à etapa 3
    assert app.session_state["contrato_etapa"] == 3
    assert app.text_input(key="wiz_valor").value == "950,00"
    assert app.text_input(key="wiz_caucao").value == "100,00"
    assert app.radio(key="wiz_periodicidade").value == "quinzenal"


def test_voltar_da_etapa_3_guarda_o_texto_invalido_para_corrigir_depois(servicos):
    app = abrir("4_Contratos.py", contrato_etapa=3, **CHAVES_WIZARD)
    app.text_input(key="wiz_valor").set_value("abc").run()
    app.button(key="wiz3_cancelar").click().run()
    assert app.session_state["contrato_etapa"] == 2
    app.button(key="wiz2_salvar").click().run()
    assert app.text_input(key="wiz_valor").value == "abc"
    assert "só números" in _texto(app)


def test_etapa_4_voltar_preserva_as_condicoes_e_criar_limpa_o_assistente(servicos):
    condicoes = {
        "data_inicio": "2026-10-01",
        "data_fim_prevista": "2026-12-01",
        "periodicidade": "mensal",
        "valor_periodo": "900.00",
        "caucao_valor": "0.00",
    }
    with patch("src.services.contratos.criar_com_vistoria", return_value={}) as criar:
        app = abrir("4_Contratos.py", contrato_etapa=4, contrato_condicoes=condicoes, **CHAVES_WIZARD)
        assert not app.exception and not app.error
        texto = _texto(app)
        assert "Pessoa teste vai alugar ABC1D23" in texto and "R$ 900,00" in texto
        app.button(key="wiz4_cancelar").click().run()
        assert app.session_state["contrato_etapa"] == 3
        assert app.session_state["contrato_condicoes"] == condicoes

        app.button(key="wiz3_salvar").click().run()
        assert app.session_state["contrato_etapa"] == 4
        app.button(key="wiz4_salvar").click().run()
    criar.assert_called_once()
    assert criar.call_args.args[0]["valor_periodo"] == "900.00"
    assert "contrato_etapa" not in app.session_state and "contrato_condicoes" not in app.session_state


def test_etapa_4_mostra_erro_da_vistoria_sem_apagar_o_formulario(servicos):
    condicoes = {
        "data_inicio": "2026-10-01",
        "data_fim_prevista": "2026-12-01",
        "periodicidade": "mensal",
        "valor_periodo": "900.00",
        "caucao_valor": "0.00",
    }
    with patch("src.services.contratos.criar_com_vistoria") as criar:
        app = abrir("4_Contratos.py", contrato_etapa=4, contrato_condicoes=condicoes, **CHAVES_WIZARD)
        app.text_area(key="entrega_extras").set_value("sem_estado")
        app.button(key="wiz4_salvar").click().run()
    criar.assert_not_called()
    assert any("nome=estado" in e.value for e in app.error)
    assert app.text_area(key="entrega_extras").value == "sem_estado"
    assert app.session_state["contrato_etapa"] == 4


# ------------------------------------------------------------------ encerramento --


def _roteiro_encerrar():
    from src.ui.contratos import _dialog_encerrar

    _dialog_encerrar(
        {"id": "ct", "moto_id": "m", "data_inicio": "2026-09-01", "km_inicial": 100},
        {"placa": "ABC1D23"},
        {"nome": "Pessoa teste"},
    )


def _futuras():
    return [
        {**COBRANCA, "id": "f1", "vencimento": "2999-01-01", "valor_pago": 0, "situacao": "aberta", "saldo": Decimal("100")},
        {**COBRANCA, "id": "f2", "vencimento": "2999-02-01", "valor_pago": 0, "situacao": "aberta", "saldo": Decimal("100")},
        {**COBRANCA, "id": "ja_pagou_parte", "vencimento": "2999-03-01", "valor_pago": 40, "situacao": "aberta"},
    ]


def test_encerrar_lista_o_que_sera_cancelado_e_exige_confirmacao(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = _futuras()
    with patch("src.services.contratos.encerrar_com_vistoria") as encerrar:
        app = _roteiro(_roteiro_encerrar)
        assert not app.exception and not app.error, [e.value for e in app.error]
        texto = _texto(app)
        assert "As 2 cobranças abaixo serão canceladas:" in texto
        assert "01/01/2999" in texto and "01/02/2999" in texto and "01/03/2999" not in texto
        assert "continuam em aberto" in texto
        assert "Marque a confirmação acima" in texto
        botao = app.button(key="perigo_enc_confirmar")
        assert botao.disabled and botao.label == "Encerrar contrato"
        # o campo "Km final" que era ignorado saiu: o km do contrato é o da vistoria de devolução
        assert not [n for n in app.number_input if n.label == "Km final"]

        app.checkbox(key="enc_confirma").check().run()
        assert not app.button(key="perigo_enc_confirmar").disabled
        app.button(key="perigo_enc_confirmar").click().run()
    encerrar.assert_called_once()
    assert encerrar.call_args.args[0] == "ct"


def test_encerrar_sem_cobrancas_futuras_diz_que_nenhuma_sera_cancelada(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = [COBRANCA]
    app = _roteiro(_roteiro_encerrar)
    assert "Nenhuma cobrança será cancelada." in _texto(app)


# ------------------------------------------------------------------ manutenção --


def _roteiro_cancelar_manutencao():
    from src.ui.manutencao import _dialog_cancelar

    _dialog_cancelar(
        {"id": "h1", "data_entrada": "2026-09-01", "descricao": "Revisão geral", "km": 100},
        {"placa": "ABC1D23", "km_atual": 100},
    )


def test_cancelar_manutencao_pede_confirmacao_explicita_e_oferece_manter(servicos):
    with patch("src.services.manutencao.finalizar") as finalizar:
        app = _roteiro(_roteiro_cancelar_manutencao)
        assert not app.exception and not app.error
        assert "O que acontece ao cancelar" in _texto(app) and "Revisão geral" in _texto(app)
        assert app.button(key="manfin_cancelar").label == "Manter manutenção"
        assert app.button(key="perigo_manfin_confirmar").disabled
        assert "Marque a confirmação acima para cancelar a manutenção." in _texto(app)

        app.checkbox(key="manfin_confirma").check().run()
        app.button(key="perigo_manfin_confirmar").click().run()
    finalizar.assert_called_once()
    assert finalizar.call_args.args[:2] == ("h1", "cancelada")


def test_registrar_manutencao_bloqueia_ate_haver_descricao_e_valores_validos(servicos):
    from tests.test_registros_ui import _abrir_dialogo_registrar

    app = _abrir_dialogo_registrar()
    assert app.button(key="manreg_salvar").disabled
    assert "Descrição: informe o serviço realizado." in _texto(app)

    app.text_area(key="manreg_descricao").set_value("Freios").run()
    assert not app.button(key="manreg_salvar").disabled

    app.text_input(key="manreg_mao_obra").set_value("dez").run()
    assert app.button(key="manreg_salvar").disabled
    assert "Custo de mão de obra: use só números" in _texto(app)
    app.text_input(key="manreg_mao_obra").set_value("1.250,50").run()
    assert not app.button(key="manreg_salvar").disabled
    assert "R$ 1.250,50" in _texto(app)  # custo total


def test_registrar_manutencao_nao_apaga_os_campos_quando_o_servico_falha(servicos):
    from tests.test_registros_ui import _abrir_dialogo_registrar

    with patch("src.services.manutencao.registrar_manutencao", side_effect=ValueError("Km menor que o atual.")):
        app = _abrir_dialogo_registrar()
        app.text_area(key="manreg_descricao").set_value("Freios").run()
        app.text_input(key="manreg_oficina").set_value("Central")
        app.button(key="manreg_salvar").click().run()
    assert any("Km menor que o atual." in e.value for e in app.error)
    assert app.text_area(key="manreg_descricao").value == "Freios"
    assert app.text_input(key="manreg_oficina").value == "Central"


# ------------------------------------------------------------------ pagamento --


def _roteiro_pagamento():
    from src.ui.cobrancas import _dialog_pagamento

    _dialog_pagamento(
        {"id": "c", "tipo": "locacao", "vencimento": "2026-09-01", "saldo": 60, "placa": "ABC1D23", "cliente": "Pessoa teste"}
    )


def _principal(app):
    return next(e for e in app.text_input if e.key.startswith("pg_principal_"))


def test_pagamento_mostra_motivo_quando_o_principal_excede_o_saldo(servicos):
    app = _roteiro(_roteiro_pagamento)
    assert _principal(app).value == "60,00"
    assert not app.button(key="pagamento_salvar").disabled
    _principal(app).set_value("80,00").run()
    assert app.button(key="pagamento_salvar").disabled
    assert "Principal recebido: não pode ser maior que o saldo da cobrança (R$ 60,00)." in _texto(app)
    _principal(app).set_value("0").run()
    assert "Principal recebido: informe um valor maior que zero." in _texto(app)


def test_pagamento_com_falha_mantem_os_valores_digitados(servicos):
    servicos["cobrancas.registrar_pagamento"].side_effect = ValueError("Cobrança já quitada.")
    app = _roteiro(_roteiro_pagamento)
    _principal(app).set_value("30,50").run()
    app.button(key="pagamento_salvar").click().run()
    assert any("Cobrança já quitada." in e.value for e in app.error)
    assert _principal(app).value == "30,50"


# ------------------------------------------------------------------ código --


def test_formularios_nao_montam_linhas_de_campos_com_colunas_soltas():
    for nome in ("documentos", "motos", "clientes", "manutencao", "vistorias", "configuracoes", "cobrancas"):
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "col1, col2 = st.columns" not in codigo, nome
    assert "st.columns(" not in (UI / "documentos.py").read_text(encoding="utf-8")
    wizard = (UI / "contratos.py").read_text(encoding="utf-8")
    inicio, fim = wizard.index("def _guardar_rascunho"), wizard.index("def _dialog_encerrar")
    assert "st.columns(" not in wizard[inicio:fim]


def test_formularios_usam_rodape_padrao_e_nao_botoes_soltos_em_colunas():
    for nome in ("documentos", "motos", "clientes", "manutencao", "vistorias", "cobrancas", "contratos"):
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "rodape_formulario(" in codigo, nome
        assert "col_cancelar" not in codigo and "col_salvar" not in codigo, nome


def test_valor_monetario_nao_usa_text_input_cru_nos_formularios():
    for nome in ("documentos", "motos", "manutencao", "cobrancas", "contratos", "configuracoes"):
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "(R$)" not in codigo, f"{nome}: o prefixo R$ vem do campo_moeda"


def test_css_dos_formularios_responde_ao_proprio_conteiner():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    assert 'st-key-rodape_' in css and "@container (max-width: 22rem)" in css
    assert "st-key-camposlinha_" in css and "flex-wrap: wrap" in css
    assert "st-key-contrato_periodicidade" not in css
    for linha in css.splitlines():
        assert not ("stColumn" in linha and "nth-child" in linha), linha[:120]


# ------------------------------------------------------- caução e danos (14.3) --


def _com_caucao(valor_pago):
    return [{**COBRANCA, "id": "cau", "tipo": "caucao", "vencimento": "2026-09-01", "valor": Decimal("1000"),
             "valor_pago": valor_pago, "saldo": Decimal("1000") - Decimal(str(valor_pago)),
             "situacao": "paga" if valor_pago >= 1000 else "aberta"}]


def test_encerrar_sem_danos_devolve_a_caucao_inteira(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = _com_caucao(1000)
    with patch("src.services.contratos.encerrar_com_vistoria") as encerrar:
        app = _roteiro(_roteiro_encerrar)
        assert "devolver ao cliente" in _texto(app) and "R$ 1.000,00" in _texto(app)
        app.checkbox(key="enc_confirma").check().run()
        app.button(key="perigo_enc_confirmar").click().run()
    assert encerrar.call_args.args[3] == Decimal("0.00")


def test_encerrar_com_dano_menor_que_a_caucao_mostra_e_envia_o_desconto(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = _com_caucao(1000)
    with patch("src.services.contratos.encerrar_com_vistoria") as encerrar:
        app = _roteiro(_roteiro_encerrar)
        app.text_input(key="enc_danos").set_value("300,00").run()
        texto = _texto(app)
        assert "Caução recebida R$ 1.000,00 − danos R$ 300,00" in texto and "R$ 700,00" in texto
        assert "Os danos passam da caução" not in texto
        # dano sem descrição não deixa encerrar
        app.checkbox(key="enc_confirma").check().run()
        assert app.button(key="perigo_enc_confirmar").disabled
        assert "Descrição dos danos: informe o que foi danificado." in _texto(app)
        app.text_area(key="enc_danos_descricao").set_value("Retrovisor quebrado").run()
        assert not app.button(key="perigo_enc_confirmar").disabled
        app.button(key="perigo_enc_confirmar").click().run()
    encerrar.assert_called_once()
    assert encerrar.call_args.args[3] == Decimal("300.00")
    assert encerrar.call_args.args[4] == "Retrovisor quebrado"


def test_encerrar_com_dano_maior_que_a_caucao_avisa_da_cobranca_do_excedente(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = _com_caucao(1000)
    app = _roteiro(_roteiro_encerrar)
    app.text_input(key="enc_danos").set_value("1.300,00").run()
    texto = _texto(app)
    assert "Os danos passam da caução: será criada uma cobrança de" in texto and "R$ 300,00" in texto
    assert "R$ 0,00" in texto  # nada a devolver


def test_encerrar_recusa_dano_invalido_e_nomeia_o_campo(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = _com_caucao(1000)
    app = _roteiro(_roteiro_encerrar)
    app.text_input(key="enc_danos").set_value("abc").run()
    app.checkbox(key="enc_confirma").check().run()
    assert app.button(key="perigo_enc_confirmar").disabled
    assert "Danos a descontar da caução" in _texto(app)


def test_encerrar_sem_caucao_recebida_nao_mostra_devolucao(servicos):
    servicos["cobrancas.listar_por_contrato"].return_value = [COBRANCA]
    app = _roteiro(_roteiro_encerrar)
    assert "devolver ao cliente" not in _texto(app)

