"""Feedback, carregamento e recuperação (Plano de melhorias, Etapa 7): mensagens específicas,
toast × alerta, falhas diferenciadas com ação de nova tentativa e envio sem duplicidade."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from postgrest.exceptions import APIError
from streamlit.testing.v1 import AppTest

from tests.test_telas_dados import servicos  # noqa: F401  (fixture)

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"


def _roteiro(funcao, default_timeout=20):
    return AppTest.from_function(funcao, default_timeout=default_timeout).run()


def _texto(elementos):
    return " ".join(e.value for e in elementos)


# ------------------------------------------------------------ sucesso (toast) --


def _roteiro_pendentes():
    from src.domain import mensagens
    from src.ui import feedback

    if "avisos" in __import__("streamlit").session_state:
        feedback.avisar(mensagens.moto_salva("ABC-1D23", nova=True))
        feedback.avisar(mensagens.contrato_criado("Maria", "ABC-1D23"))
        feedback.avisar(mensagens.vistoria_registrada("entrega", "ABC-1D23", falhas_fotos=1))
    feedback.exibir_pendentes()


def test_confirmacao_simples_vira_toast_e_o_que_pede_atencao_fica_na_tela():
    app = AppTest.from_function(_roteiro_pendentes, default_timeout=20)
    app.session_state["avisos"] = True
    app.run()
    assert [t.value for t in app.toast] == ["Moto ABC-1D23 cadastrada."]
    assert "Anexe as fotos da vistoria de entrega" in _texto(app.success)
    assert "Use “Adicionar fotos” para tentar de novo" in _texto(app.warning)


def test_avisos_aparecem_uma_vez_so():
    app = AppTest.from_function(_roteiro_pendentes, default_timeout=20)
    app.session_state["avisos"] = True
    app.run()
    del app.session_state["avisos"]
    app.run()
    assert not app.toast and not app.success and not app.warning


def test_cifrao_nao_vira_formula_no_toast_nem_no_alerta():
    def roteiro():
        from decimal import Decimal

        from src.domain import mensagens
        from src.ui import feedback

        feedback.avisar(mensagens.pagamento_registrado(Decimal("60"), Decimal("3"), quitada=True))
        feedback.avisar(mensagens.contrato_criado("Maria R$ 1", "ABC-1D23"))
        feedback.exibir_pendentes()

    app = _roteiro(roteiro)
    assert app.toast[0].value.count(r"R\$") == 2  # dois R$ no mesmo texto virariam fórmula sem o escape
    assert r"R\$ 1" in app.success[0].value


def test_toast_usa_duracao_longa_para_dar_tempo_de_ler():
    codigo = (UI / "feedback.py").read_text(encoding="utf-8")
    assert 'duration="long"' in codigo


# ----------------------------------------------------------------- falhas --


def _roteiro_falha():
    import httpx
    import streamlit as st
    from postgrest.exceptions import APIError

    from src.ui.componentes import proteger

    tipo = st.session_state["tipo_falha"]
    tentativas = st.session_state.get("tentativas", 0)
    st.session_state["tentativas"] = tentativas + 1
    erros = {
        "validacao": ValueError("Valor: informe um número maior que zero."),
        "rede": httpx.ConnectError("sem rede"),
        "sessao": APIError({"message": "JWT expired", "code": "PGRST301", "hint": None, "details": None}),
        "permissao": APIError({"message": "negado", "code": "42501", "hint": None, "details": None}),
    }
    with proteger(nova_tentativa=st.session_state.get("pagina", True)):
        if tipo != "rede_uma_vez" or tentativas == 0:
            raise erros["rede" if tipo == "rede_uma_vez" else tipo]
        st.write("Carregou.")


def _abrir(tipo, pagina=True):
    app = AppTest.from_function(_roteiro_falha, default_timeout=20)
    app.session_state["tipo_falha"] = tipo
    app.session_state["pagina"] = pagina
    return app.run()


def test_erro_de_validacao_mostra_a_mensagem_sem_oferecer_repetir():
    app = _abrir("validacao")
    assert "Valor: informe um número maior que zero." in _texto(app.error)
    assert not app.button


def test_indisponibilidade_de_consulta_oferece_tentar_novamente_e_funciona():
    app = _abrir("rede_uma_vez")
    assert "tente novamente" in _texto(app.error)
    botao = next(b for b in app.button if b.label == "Tentar novamente")
    botao.click().run()
    assert not app.error
    assert any(m.value == "Carregou." for m in app.markdown)


def test_indisponibilidade_em_formulario_orienta_enviar_de_novo_sem_botao_solto():
    def roteiro():
        import httpx
        import streamlit as st

        from src.ui.componentes import proteger

        with st.form("f"):
            enviado = st.form_submit_button("Salvar")
            if enviado:
                with proteger():
                    raise httpx.ConnectError("sem rede")

    app = _roteiro(roteiro)
    app.button[0].click().run()
    assert not app.exception
    assert "O que você digitou continua no formulário; envie de novo." in _texto(app.error)
    assert [b.label for b in app.button] == ["Salvar"]


def test_sessao_expirada_pede_novo_login_com_botao():
    app = _abrir("sessao")
    assert "Entre novamente" in _texto(app.warning)
    assert any(b.label == "Entrar novamente" for b in app.button)


def test_sessao_expirada_dentro_de_formulario_nao_quebra_a_tela():
    def roteiro():
        import streamlit as st
        from postgrest.exceptions import APIError

        from src.ui.componentes import proteger

        with st.form("f"):
            if st.form_submit_button("Salvar"):
                with proteger():
                    raise APIError({"message": "JWT expired", "code": "PGRST301", "hint": None, "details": None})

    app = _roteiro(roteiro)
    app.button[0].click().run()
    assert not app.exception
    assert "Entre novamente" in _texto(app.warning)
    assert any("Recarregue a página" in c.value for c in app.caption)


def test_falta_de_permissao_informa_sem_oferecer_repetir():
    app = _abrir("permissao")
    assert "não permite esta operação" in _texto(app.error)
    assert not app.button


# ------------------------------------------------------- chave de operação --


def _roteiro_chave():
    import streamlit as st

    from src.ui import feedback

    conteudo = st.session_state["conteudo"]
    st.session_state.setdefault("chaves", []).append(feedback.chave_operacao("demo", conteudo))
    if st.session_state.get("encerrar"):
        feedback.encerrar_operacao("demo")


def test_chave_de_operacao_repete_no_mesmo_envio_e_muda_quando_o_conteudo_muda():
    app = AppTest.from_function(_roteiro_chave, default_timeout=20)
    app.session_state["conteudo"] = {"valor": "10"}
    app.run().run()
    primeira, repetida = app.session_state["chaves"]
    assert primeira == repetida
    app.session_state["conteudo"] = {"valor": "20"}
    app.run()
    assert app.session_state["chaves"][-1] != primeira


def test_chave_de_operacao_encerrada_nao_e_reaproveitada():
    app = AppTest.from_function(_roteiro_chave, default_timeout=20)
    app.session_state["conteudo"] = {"valor": "10"}
    app.session_state["encerrar"] = True
    app.run().run()
    primeira, segunda = app.session_state["chaves"]
    assert primeira != segunda


def test_cancelar_o_formulario_descarta_a_chave_de_operacao():
    def roteiro():
        import streamlit as st

        from src.ui import feedback
        from src.ui.formularios import rodape_formulario

        feedback.chave_operacao("demo", {"valor": "10"})
        acao = rodape_formulario("Salvar", "demo")
        st.session_state["cancelou"] = acao.cancelou

    app = _roteiro(roteiro)
    assert "operacao_demo" in app.session_state
    app.button(key="demo_cancelar").click().run()
    assert app.session_state["cancelou"] is True
    assert "operacao_demo" not in app.session_state


# ------------------------------------------------ pagamento: mensagem e chave --


def _roteiro_pagamento():
    from src.ui.cobrancas import _dialog_pagamento

    _dialog_pagamento(
        {"id": "c", "tipo": "locacao", "vencimento": "2026-09-01", "saldo": 450, "placa": "ABC1D23", "cliente": "Pessoa teste"}
    )


def test_pagamento_informa_o_valor_e_envia_a_chave_de_operacao(servicos):
    app = _roteiro(_roteiro_pagamento)
    principal = next(e for e in app.text_input if e.key.startswith("pg_principal_"))
    principal.set_value("450,00").run()
    app.button(key="pagamento_salvar").click().run()
    assert not app.error, [e.value for e in app.error]
    chamada = servicos["cobrancas.registrar_pagamento"].call_args
    assert len(chamada.kwargs["chave_operacao"]) == 36  # uuid
    avisos = app.session_state["feedback_pendentes"]
    assert avisos[0][0].startswith("Pagamento de R$ 450,00 registrado.")
    assert "Cobrança quitada." in avisos[0][0]
    assert "operacao_pagamento" not in app.session_state


def test_pagamento_com_falha_mantem_a_chave_para_a_nova_tentativa(servicos):
    servicos["cobrancas.registrar_pagamento"].side_effect = [ValueError("Sem conexão."), {}]
    app = _roteiro(_roteiro_pagamento)
    app.button(key="pagamento_salvar").click().run()
    primeira = servicos["cobrancas.registrar_pagamento"].call_args.kwargs["chave_operacao"]
    app.button(key="pagamento_salvar").click().run()
    segunda = servicos["cobrancas.registrar_pagamento"].call_args.kwargs["chave_operacao"]
    assert primeira == segunda


# ------------------------------------------------- repositório idempotente --


def _api(codigo, mensagem):
    return APIError({"message": mensagem, "code": codigo, "hint": None, "details": None})


def _cliente_falso(existente=None, erro=None):
    tabela = MagicMock()
    consulta = tabela.select.return_value.eq.return_value.limit.return_value.execute
    consulta.return_value.data = [existente] if existente else []
    if erro:
        tabela.insert.return_value.execute.side_effect = erro
    else:
        tabela.insert.return_value.execute.return_value.data = [{"id": "novo"}]
    cliente = MagicMock()
    cliente.table.return_value = tabela
    return cliente, tabela


def test_repositorio_sem_chave_apenas_insere():
    from src.repositories.consultas import inserir_idempotente

    cliente, tabela = _cliente_falso()
    with patch("src.repositories.consultas.get_client", return_value=cliente):
        assert inserir_idempotente("pagamentos", {"valor": "1"}) == {"id": "novo"}
    tabela.select.assert_not_called()
    tabela.insert.assert_called_once_with({"valor": "1"})


def test_repositorio_devolve_o_registro_ja_gravado_sem_inserir_de_novo():
    from src.repositories.consultas import inserir_idempotente

    cliente, tabela = _cliente_falso(existente={"id": "antigo"})
    with patch("src.repositories.consultas.get_client", return_value=cliente):
        assert inserir_idempotente("pagamentos", {"valor": "1"}, "k1") == {"id": "antigo"}
    tabela.insert.assert_not_called()


def test_repositorio_grava_a_chave_junto_com_o_registro():
    from src.repositories.consultas import inserir_idempotente

    cliente, tabela = _cliente_falso()
    with patch("src.repositories.consultas.get_client", return_value=cliente):
        inserir_idempotente("pagamentos", {"valor": "1"}, "k1")
    tabela.insert.assert_called_once_with({"valor": "1", "chave_operacao": "k1"})


def test_repositorio_trata_envio_simultaneo_como_repeticao():
    from src.repositories.consultas import inserir_idempotente

    cliente, tabela = _cliente_falso(erro=_api("23505", 'duplicate key "uq_pagamentos_chave_operacao"'))
    consulta = tabela.select.return_value.eq.return_value.limit.return_value.execute
    consulta.side_effect = [MagicMock(data=[]), MagicMock(data=[{"id": "do-outro-envio"}])]
    with patch("src.repositories.consultas.get_client", return_value=cliente):
        assert inserir_idempotente("pagamentos", {"valor": "1"}, "k1") == {"id": "do-outro-envio"}


def test_repositorio_nao_esconde_outros_conflitos():
    import pytest

    from src.repositories.consultas import inserir_idempotente

    cliente, _ = _cliente_falso(erro=_api("23505", 'unique constraint "motos_placa_key"'))
    with patch("src.repositories.consultas.get_client", return_value=cliente):
        with pytest.raises(APIError):
            inserir_idempotente("motos", {"placa": "ABC1D23"}, "k1")


# ----------------------------------------------------- estado ocupado e CSS --


def test_script_do_estado_ocupado_cobre_rodapes_e_botoes_ocupa():
    codigo = (UI / "feedback.py").read_text(encoding="utf-8")
    assert 'st-key-rodape_' in codigo and 'st-key-ocupa_' in codigo
    assert "stopImmediatePropagation" in codigo  # segundo clique não passa enquanto ocupado
    assert "data-test-script-state" in codigo  # termina quando a execução acaba


def test_css_do_estado_ocupado_troca_o_rotulo_e_nao_aceita_clique():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    assert 'button[data-ocupado]' in css
    assert "Salvando…" in css
    assert "pointer-events: none" in css[css.index("button[data-ocupado]") :][:900]


def test_toast_cabe_em_tela_estreita_e_nao_cobre_o_conteudo_sem_ser_dispensavel():
    css = (UI / "estilos.css").read_text(encoding="utf-8")
    bloco = css[css.index("stToastContainer") :][:900]
    assert "max-width" in bloco and "100vw" in bloco


def test_nenhuma_tela_usa_mais_a_confirmacao_generica():
    for caminho in UI.glob("*.py"):
        codigo = caminho.read_text(encoding="utf-8")
        assert "Alterações salvas" not in codigo, caminho.name
        assert "mensagem_sucesso" not in codigo, caminho.name
        assert "def _salvo" not in codigo, caminho.name


def test_portal_do_cliente_nao_usa_colunas_soltas_para_as_acoes():
    codigo = (UI / "clientes_portal.py").read_text(encoding="utf-8")
    assert "st.columns" not in codigo
    assert 'key="portal_acoes"' in codigo


def test_paginas_oferecem_nova_tentativa_nas_consultas():
    for nome in ("motos", "clientes", "contratos", "cobrancas", "documentos", "manutencao", "vistorias",
                 "dashboard", "relatorios", "configuracoes", "portal_locatario"):
        codigo = (UI / f"{nome}.py").read_text(encoding="utf-8")
        assert "proteger(nova_tentativa=True)" in codigo, nome
