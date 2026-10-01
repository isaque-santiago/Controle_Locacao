"""Contratos: lista, assistente de novo contrato e ficha — segue Contratos.dc.html,
ContratoNovo.dc.html e ContratoFicha.dc.html do mockup."""

from datetime import date, timedelta
from html import escape

import streamlit as st

from src.services import contratos, motos, clientes, cobrancas, vistorias, manutencao
from src.domain.encerramento import cobrancas_a_cancelar
from src.domain.entradas import decimal_campo, erro_de, primeiro_erro
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import (
    cabecalho,
    cabecalho_pagina,
    vazio_lista,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    tabela_html,
    abrir_ficha_cliente,
    botao_acao,
    botao_voltar,
    indicador_etapas,
)
from src.ui.formularios import campo_moeda, legenda_obrigatorios, linha_campos, rodape_formulario, rotulo_obrigatorio
from src.ui.listas import abas, aba_ativa, barra_filtros, paginar, reiniciar_abas, rodape_paginacao
from src.ui.registros import campo, lista_registros, registro
from src.ui.formatadores import formatar_data, formatar_moeda, mascarar_cpf
from src.ui.vistorias import campos as campos_vistoria, preparar as preparar_vistoria

_STATUS_ROTULO = {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}
_OPCOES_FILTRO = [("Todos", "Todos")] + [(chave, _STATUS_ROTULO[chave]) for chave in ("ativo", "encerrado", "cancelado")]
_PERIODOS = ["diario", "semanal", "quinzenal", "mensal"]
_PERIODOS_ROTULO = {"diario": "Diário", "semanal": "Semanal", "quinzenal": "Quinzenal", "mensal": "Mensal"}
_ETAPAS_WIZARD = ["Cliente", "Moto", "Condições", "Confirmar"]
_LIMITE_IMPACTO = 8  # cobranças listadas no diálogo de encerramento; as demais viram "e mais N"


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


_CHAVES_WIZARD = (
    "contratos_visao",
    "contratos_id_selecionado",
    "contrato_etapa",
    "contrato_cliente_id",
    "contrato_moto_id",
    "contrato_condicoes",
    "contrato_rascunho",
    "wiz_inicio",
    "wiz_fim",
    "wiz_valor",
    "wiz_caucao",
    "wiz_periodicidade",
)


def _ir_para_lista():
    for chave in _CHAVES_WIZARD:
        st.session_state.pop(chave, None)
    st.rerun()


def _ir_para_ficha(contrato_id):
    reiniciar_abas("contratos_ficha_abas")
    st.session_state["contratos_visao"] = "ficha"
    st.session_state["contratos_id_selecionado"] = contrato_id
    st.rerun()


def _iniciar_wizard():
    for chave in _CHAVES_WIZARD:
        st.session_state.pop(chave, None)
    st.session_state["contratos_visao"] = "wizard"
    st.session_state["contrato_etapa"] = 1
    st.rerun()


def _iniciais(nome):
    return (nome or "?").strip()[:1].upper()


# ------------------------------------------------------------------ lista --

def _exibir_lista():
    registros = contratos.listar()
    contagem = {
        chave: sum(1 for c in registros if c["status"] == chave)
        for chave in ("ativo", "encerrado", "cancelado")
    }
    frota = {m["id"]: m for m in motos.listar()}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}

    if cabecalho_pagina(
        "Contratos",
        sub=f"{contagem.get('ativo', 0)} contrato(s) ativo(s)",
        acao={"rotulo": "Novo contrato", "chave": "contratos_novo"},
    ):
        _iniciar_wizard()

    filtros = barra_filtros(
        "contratos",
        _OPCOES_FILTRO,
        padrao="ativo",
        contagens={"Todos": len(registros), **contagem},
        busca="Buscar por cliente ou placa",
    )
    busca = filtros.busca.casefold()
    filtrados = [
        c
        for c in registros
        if (filtros.valor == "Todos" or c["status"] == filtros.valor)
        and (
            busca in nomes.get(c["cliente_id"], "").casefold()
            or busca in frota.get(c["moto_id"], {}).get("placa", "").casefold()
        )
    ]
    filtrados.sort(key=lambda c: c["data_inicio"], reverse=True)
    filtros.resumo(len(filtrados), ("contrato", "contratos"))
    pagina_atual, pagina = paginar("contratos", filtrados)

    with lista_registros("contratos", acoes=1):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhum contrato encontrado.", "Ainda não há contratos cadastrados.", bool(registros), "Novo contrato"),
                unsafe_allow_html=True,
            )
        for contrato in pagina_atual:
            moto = frota.get(contrato["moto_id"])
            muted = "color:var(--texto-3);" if contrato["status"] != "ativo" else ""
            nome = nomes.get(contrato["cliente_id"], "—")
            periodo = _PERIODOS_ROTULO.get(contrato["periodicidade"], contrato["periodicidade"])
            campos = [
                campo("Moto", chip_placa(moto["placa"]) if moto else "—"),
                campo("Início", f'<span class="mono" style="font-size:var(--fs-secundario);{muted}">{formatar_data(contrato["data_inicio"])}</span>'),
                campo("Periodicidade", f'<span style="font-size:var(--fs-secundario);{muted or "color:var(--texto-2);"}">{escape(periodo)}</span>'),
                campo("Valor / período", f'<span class="mono" style="font-size:var(--fs-secundario);{muted}">{formatar_moeda(contrato["valor_periodo"])}</span>'),
            ]
            with registro(
                "contratos",
                contrato["id"],
                f'<span style="{muted}">{escape(nome)}</span>',
                campos,
                selo=selo_situacao(_STATUS_ROTULO[contrato["status"]], contrato["status"]),
            ) as acoes:
                if botao_acao(
                    acoes,
                    "abrir",
                    f"ficha_ct_{contrato['id']}",
                    ajuda=f"Abrir o contrato de {nomes.get(contrato['cliente_id'], 'cliente')}",
                ):
                    _ir_para_ficha(contrato["id"])

    rodape_paginacao("contratos", pagina)


# ----------------------------------------------------------------- wizard --

def _avatar_circulo(texto, cor="var(--chip-fundo)"):
    return (
        f'<div style="width:30px;height:30px;border-radius:50%;background:{cor};color:var(--chip-texto);'
        f'display:flex;align-items:center;justify-content:center;font-size:var(--fs-legenda);font-weight:600;'
        f'flex-shrink:0;">{texto}</div>'
    )


def _cartao_selecionavel(chave, icone_html, titulo, subtitulo, badge_html, selecionado, elegivel):
    """Opção de escolha do assistente: identidade + situação e um botão `Selecionar`. A opção
    escolhida muda o texto do botão para `Selecionado` (não depende só da cor da borda)."""
    estado = "selecionado" if selecionado else (None if elegivel else "indisponivel")
    identidade = f'<span style="display:inline-flex;align-items:center;gap:12px;">{icone_html}<span>{escape(titulo)}</span></span>'
    with registro(
        "contrato_selecao",
        chave,
        identidade,
        [],
        selo=badge_html or None,
        subtitulo=f'<span class="mono">{subtitulo}</span>',
        estado=estado,
    ) as acoes:
        return botao_acao(
            acoes,
            "selecionar",
            f"sel_{chave}",
            rotulo="Selecionado" if selecionado else None,
            icone=":material/check_circle:" if selecionado else None,
            ajuda=f"Escolher {titulo}",
            desabilitado=not elegivel,
        )


def _wizard_etapa1():
    pessoas = clientes.listar()
    contratos_ativos = {c["cliente_id"]: c["moto_id"] for c in contratos.listar() if c["status"] == "ativo"}
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    busca = st.text_input(
        "Buscar", placeholder="Buscar cliente por nome ou CPF", label_visibility="collapsed", key="wizard_busca_cliente"
    )
    busca_normalizada = busca.casefold()
    candidatos = [
        c
        for c in pessoas
        if busca_normalizada in c["nome"].casefold() or busca_normalizada in (c.get("cpf") or "")
    ]
    selecionado_id = st.session_state.get("contrato_cliente_id")
    if not candidatos:
        st.info("Nenhum cliente encontrado.")
    with lista_registros("contrato_selecao_clientes", acoes=1):
        for cliente in candidatos:
            elegivel = cliente["status"] == "ativo"
            moto_atual = contratos_ativos.get(cliente["id"])
            if not elegivel:
                badge = f'<span style="font-size:var(--fs-legenda);color:var(--perigo-texto);">{"bloqueado" if cliente["status"] == "bloqueado" else "inativo"} · não pode alugar</span>'
            elif moto_atual:
                badge = f'<span style="font-size:var(--fs-legenda);color:var(--texto-2);">já aluga {escape(placas.get(moto_atual, "—"))}</span>'
            else:
                badge = ""
            avatar_cor = "var(--chip-fundo)" if elegivel else "var(--avatar-inativo)"
            if _cartao_selecionavel(
                f"cli_card_{cliente['id']}",
                _avatar_circulo(escape(_iniciais(cliente["nome"])), avatar_cor),
                cliente["nome"],
                escape(mascarar_cpf(cliente.get("cpf") or "")).replace("*", "&#42;"),
                badge,
                selecionado_id == cliente["id"],
                elegivel,
            ):
                st.session_state["contrato_cliente_id"] = cliente["id"]
                st.rerun()


def _wizard_etapa2():
    frota = [m for m in motos.listar() if m["status"] == "disponivel"]
    busca = st.text_input(
        "Buscar", placeholder="Buscar moto disponível por placa ou modelo",
        label_visibility="collapsed", key="wizard_busca_moto",
    )
    busca_normalizada = busca.casefold()
    candidatos = [
        m for m in frota
        if busca_normalizada in m["placa"].casefold() or busca_normalizada in f"{m['marca']} {m['modelo']}".casefold()
    ]
    selecionado_id = st.session_state.get("contrato_moto_id")
    if not candidatos:
        st.info("Nenhuma moto disponível encontrada.")
    with lista_registros("contrato_selecao_motos", acoes=1):
        for moto in candidatos:
            km_fmt = f"{moto['km_atual']:,}".replace(",", ".")
            sugerida = formatar_moeda(moto.get("valor_locacao_sugerido")) if moto.get("valor_locacao_sugerido") else "—"
            if _cartao_selecionavel(
                f"moto_card_{moto['id']}",
                chip_placa(moto["placa"]),
                f"{moto['marca']} {moto['modelo']}",
                f"{km_fmt} km · sugerida {sugerida}/mês",
                "",
                selecionado_id == moto["id"],
                True,
            ):
                st.session_state["contrato_moto_id"] = moto["id"]
                st.rerun()


def _guardar_rascunho():
    """Guarda o que a etapa 3 já tem nos campos (mesmo inválido), para voltar e revisar etapas
    anteriores sem perder o progresso. Campos de widget somem do estado quando saem da tela."""
    rascunho = dict(st.session_state.get("contrato_rascunho", {}))
    for chave, campo_estado in (
        ("data_inicio", "wiz_inicio"),
        ("data_fim_prevista", "wiz_fim"),
        ("valor_periodo", "wiz_valor"),
        ("caucao_valor", "wiz_caucao"),
        ("periodicidade", "wiz_periodicidade"),
    ):
        if campo_estado in st.session_state:
            valor = st.session_state[campo_estado]
            rascunho[chave] = valor.isoformat() if isinstance(valor, date) else valor
    st.session_state["contrato_rascunho"] = rascunho


def _ir_para_etapa(etapa):
    """Troca de etapa sem perder cliente, moto nem condições (também usado como `on_click`)."""
    _guardar_rascunho()
    st.session_state["contrato_etapa"] = etapa


def _resumo_selecao(cliente, moto, etapa):
    """Cliente e moto já escolhidos, com `Alterar` para revisar a etapa correspondente."""
    with st.container(key="wizard_resumo"):
        st.markdown(
            f'<div class="wizard-resumo"><span><span class="wizard-resumo__rotulo">Cliente</span> {escape(cliente["nome"])}</span>'
            f'<span><span class="wizard-resumo__rotulo">Moto</span> {chip_placa(moto["placa"])} '
            f'{escape(moto["marca"])} {escape(moto["modelo"])}</span></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="wizard_resumo_acoes"):
            st.button(
                "Alterar cliente",
                key=f"alterar_cliente_{etapa}",
                icon=":material/edit:",
                type="tertiary",
                on_click=_ir_para_etapa,
                args=(1,),
            )
            st.button(
                "Alterar moto",
                key=f"alterar_moto_{etapa}",
                icon=":material/edit:",
                type="tertiary",
                on_click=_ir_para_etapa,
                args=(2,),
            )


def _dados_selecionados():
    moto = next(m for m in motos.listar() if m["id"] == st.session_state["contrato_moto_id"])
    cliente = next(c for c in clientes.listar() if c["id"] == st.session_state["contrato_cliente_id"])
    return cliente, moto


def _texto_rascunho(rascunho, chave, campo_estado):
    """Texto digitado antes de sair da etapa, enquanto o campo ainda não voltou ao estado."""
    return rascunho.get(chave) if chave in rascunho and campo_estado not in st.session_state else None


def _wizard_etapa3():
    cliente, moto = _dados_selecionados()
    _resumo_selecao(cliente, moto, 3)
    rascunho = st.session_state.get("contrato_rascunho") or st.session_state.get("contrato_condicoes", {})
    hoje = hoje_br()

    with linha_campos([1, 1], "wiz_datas") as (col_inicio, col_fim):
        with col_inicio:
            inicio = campo_data(
                rotulo_obrigatorio("Data de início"), rascunho.get("data_inicio") or hoje.isoformat(), key="wiz_inicio"
            )
        with col_fim:
            fim = campo_data(
                rotulo_obrigatorio("Fim previsto"),
                rascunho.get("data_fim_prevista") or (hoje + timedelta(days=30)).isoformat(),
                key="wiz_fim",
                help="O prazo é obrigatório nesta versão do assistente.",
            )
    periodicidade = st.radio(
        "Periodicidade",
        _PERIODOS,
        index=_PERIODOS.index(rascunho.get("periodicidade", "mensal")),
        format_func=_PERIODOS_ROTULO.get,
        horizontal=True,
        key="wiz_periodicidade",
    )
    with linha_campos([1, 1], "wiz_valores") as (col_valor, col_caucao):
        with col_valor:
            valor = campo_moeda(
                "Valor do período",
                moto.get("valor_locacao_sugerido"),
                "wiz_valor",
                obrigatorio=True,
                ao_vivo=True,
                texto=_texto_rascunho(rascunho, "valor_periodo", "wiz_valor"),
            )
        with col_caucao:
            caucao = campo_moeda(
                "Caução",
                0,
                "wiz_caucao",
                ao_vivo=True,
                texto=_texto_rascunho(rascunho, "caucao_valor", "wiz_caucao"),
            )
    st.caption(f"Km inicial: {moto['km_atual']:,} km (leitura atual da moto).".replace(",", "."))
    legenda_obrigatorios()

    erro = primeiro_erro(
        None if inicio else "Data de início: informe a data.",
        None if fim else "Fim previsto: informe a data.",
        "Fim previsto: escolha uma data igual ou posterior ao início." if inicio and fim and fim < inicio else None,
        erro_de(decimal_campo, valor, "Valor do período", positivo=True),
        erro_de(decimal_campo, caucao, "Caução"),
    )
    acao = rodape_formulario("Avançar", "wiz3", desabilitado=bool(erro), motivo=erro, cancelar="Voltar")
    if acao.cancelou:
        _ir_para_etapa(2)
        st.rerun()
    if acao.confirmou:
        st.session_state["contrato_condicoes"] = {
            "data_inicio": inicio.isoformat(),
            "data_fim_prevista": fim.isoformat(),
            "periodicidade": periodicidade,
            "valor_periodo": str(decimal_campo(valor, "Valor do período", positivo=True)),
            "caucao_valor": str(decimal_campo(caucao, "Caução")),
        }
        _ir_para_etapa(4)
        st.rerun()


def _wizard_etapa4():
    cliente, moto = _dados_selecionados()
    _resumo_selecao(cliente, moto, 4)
    condicoes = st.session_state["contrato_condicoes"]

    agenda = contratos.previa_agenda(
        date.fromisoformat(condicoes["data_inicio"]),
        condicoes["periodicidade"],
        decimal_br(condicoes["valor_periodo"], positivo=True),
        date.fromisoformat(condicoes["data_fim_prevista"]),
    )
    caucao_dec = decimal_br(condicoes["caucao_valor"])

    def item(rotulo, valor, mono=True):
        classe = "resumo-contrato__valor mono" if mono else "resumo-contrato__valor"
        return (
            f'<div class="resumo-contrato__item"><span class="resumo-contrato__rotulo">{rotulo}</span>'
            f'<span class="{classe}">{valor}</span></div>'
        )

    titulo = f"{cliente['nome']} vai alugar {moto['placa']} · {moto['marca']} {moto['modelo']}"
    st.markdown(
        f"""
        <div class="resumo-contrato">
          <div class="resumo-contrato__titulo rotulo">{escape(titulo)}</div>
          <div class="resumo-contrato__grade">
            {item("periodicidade", _PERIODOS_ROTULO[condicoes['periodicidade']], mono=False)}
            {item("valor / período", formatar_moeda(condicoes['valor_periodo']))}
            {item("início", formatar_data(condicoes['data_inicio']))}
            {item("fim previsto", formatar_data(condicoes['data_fim_prevista']))}
            {item("caução", formatar_moeda(condicoes['caucao_valor']))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown('<h3 class="rotulo wizard-secao">Prévia da agenda de cobranças</h3>', unsafe_allow_html=True)
    linhas = []
    if caucao_dec > 0:
        linhas.append(["Caução", f'<span class="mono">{formatar_data(condicoes["data_inicio"])}</span>', f'<span class="mono">{formatar_moeda(caucao_dec)}</span>'])
    for parcela in agenda:
        linhas.append(
            [
                f"Parcela {parcela['numero']}",
                f'<span class="mono">{formatar_data(parcela["vencimento"].isoformat())}</span>',
                f'<span class="mono">{formatar_moeda(parcela["valor"])}</span>',
            ]
        )
    tabela_html(["Item", "Vencimento", "Valor"], linhas, legenda="Cobranças previstas do contrato")

    st.write("")
    st.markdown('<h3 class="rotulo wizard-secao">Vistoria de entrega</h3>', unsafe_allow_html=True)
    with st.form("novo_contrato_" + moto["id"]):
        vistoria = campos_vistoria("entrega", moto["km_atual"])
        acao = rodape_formulario("Criar contrato", "wiz4", formulario=True, cancelar="Voltar")
    if acao.cancelou:
        _ir_para_etapa(3)
        st.rerun()
    if acao.confirmou:
        with proteger():
            dados_vistoria = preparar_vistoria(vistoria)
            contratos.criar_com_vistoria(
                {
                    "moto_id": moto["id"],
                    "cliente_id": cliente["id"],
                    "km_inicial": dados_vistoria["km"],
                    **condicoes,
                },
                dados_vistoria,
            )
            for chave in _CHAVES_WIZARD:
                st.session_state.pop(chave, None)
            _salvo("Contrato criado. Anexe as fotos da vistoria na página Vistorias.")


def _exibir_wizard():
    if botao_voltar("contratos", "voltar_wizard"):
        _ir_para_lista()
    etapa = st.session_state.setdefault("contrato_etapa", 1)

    cabecalho_pagina("Novo contrato", sub="Assistente em 4 etapas")
    indicador_etapas(etapa, _ETAPAS_WIZARD, nome="Etapas do novo contrato")

    if etapa == 1:
        _wizard_etapa1()
        acao = rodape_formulario(
            "Avançar",
            "wiz1",
            desabilitado=not st.session_state.get("contrato_cliente_id"),
            motivo="Selecione um cliente para continuar.",
            cancelar="Cancelar",
        )
        if acao.cancelou:
            _ir_para_lista()
        if acao.confirmou:
            st.session_state["contrato_etapa"] = 2
            st.rerun()
    elif etapa == 2:
        _wizard_etapa2()
        acao = rodape_formulario(
            "Avançar",
            "wiz2",
            desabilitado=not st.session_state.get("contrato_moto_id"),
            motivo="Selecione uma moto disponível para continuar.",
            cancelar="Voltar",
        )
        if acao.cancelou:
            st.session_state["contrato_etapa"] = 1
            st.rerun()
        if acao.confirmou:
            st.session_state["contrato_etapa"] = 3
            st.rerun()
    elif etapa == 3:
        _wizard_etapa3()
    elif etapa == 4:
        _wizard_etapa4()


# ------------------------------------------------------------------ ficha --

@st.dialog("Encerrar contrato")
def _dialog_encerrar(contrato, moto, cliente):
    st.markdown(f'{chip_placa(moto["placa"])} <span class="dialogo-identidade">{escape(cliente["nome"])}</span>', unsafe_allow_html=True)
    inicio = date.fromisoformat(str(contrato["data_inicio"])[:10])
    data = campo_data(
        rotulo_obrigatorio("Data de encerramento"), max(hoje_br(), inicio).isoformat(), key="enc_data", min_value=inicio
    )
    moto_atual = next(m for m in motos.listar() if m["id"] == contrato["moto_id"])
    vistoria = campos_vistoria(
        "devolucao", moto_atual["km_atual"], ajuda_km=f"Vale como km final do contrato (início: {contrato['km_inicial']:,} km).".replace(",", ".")
    )
    devolvida = st.checkbox("Caução devolvida ao cliente", value=True, key="enc_caucao")

    afetadas = cobrancas_a_cancelar(cobrancas.listar_por_contrato(contrato["id"]), data) if data else []
    impacto = (
        f"As {len(afetadas)} cobranças abaixo serão canceladas:" if len(afetadas) > 1
        else ("A cobrança abaixo será cancelada:" if afetadas else "Nenhuma cobrança será cancelada.")
    )
    itens = "".join(
        f'<li>{escape(c["tipo"].capitalize())} · vence <span class="mono">{formatar_data(c["vencimento"])}</span> · '
        f'<span class="mono">{formatar_moeda(c["saldo"])}</span></li>'
        for c in afetadas[:_LIMITE_IMPACTO]
    )
    resto = len(afetadas) - _LIMITE_IMPACTO
    mais = f"<li>e mais {resto} cobrança(s)</li>" if resto > 0 else ""
    st.markdown(
        '<div class="impacto" role="group" aria-label="O que o encerramento altera">'
        '<div class="impacto__titulo">O que acontece ao encerrar</div>'
        "<ul>"
        f"<li>O contrato passa a Encerrado e a moto volta a ficar disponível.</li>"
        f"<li>{impacto}</li></ul>"
        f'<ul class="impacto__lista">{itens}{mais}</ul>'
        "<p>Cobranças já vencidas até a data, ou com pagamento parcial, continuam em aberto.</p></div>",
        unsafe_allow_html=True,
    )
    confirmou_impacto = st.checkbox(
        "Entendo o que será alterado e quero encerrar o contrato.", key="enc_confirma"
    )
    erro = primeiro_erro(None if data else "Data de encerramento: informe a data.")
    motivo = erro or (None if confirmou_impacto else "Marque a confirmação acima para encerrar o contrato.")
    acao = rodape_formulario(
        "Encerrar contrato", "enc", desabilitado=bool(motivo), motivo=motivo, perigo=True
    )
    if acao.cancelou:
        st.rerun()
    if acao.confirmou:
        with proteger():
            contratos.encerrar_com_vistoria(contrato["id"], data, preparar_vistoria(vistoria), devolvida)
            _salvo("Contrato encerrado.")


def _cabecalho_ficha(contrato, moto, cliente):
    if contrato["status"] == "ativo" and moto:
        linha = f"Ativo · desde {formatar_data(contrato['data_inicio'])} · {contrato['periodicidade']}"
    else:
        linha = f"{_STATUS_ROTULO[contrato['status']]} · desde {formatar_data(contrato['data_inicio'])}"
    col_titulo, col_acao = st.columns([3, 1], vertical_alignment="center")
    with col_titulo:
        st.markdown(
            f"""
            <div class="contrato-cab">
              <h1 class="rotulo" style="margin:0;font-size:22px;"><span>{cliente['nome']}</span>
                <span class="contrato-cab__seta">→</span>
                <span class="contrato-cab__moto">{moto['marca']} {moto['modelo']} {chip_placa(moto['placa'])}</span>
              </h1>
              <div style="font-size:var(--fs-secundario);margin-top:6px;">{selo_situacao(linha, contrato["status"])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_acao:
        if st.button("Ver cliente", key="ver_cliente_contrato", icon=":material/arrow_forward:", use_container_width=True):
            abrir_ficha_cliente(cliente["id"])
        if contrato["status"] == "ativo":
            if st.button("Encerrar contrato", key="abrir_encerrar", use_container_width=True):
                _dialog_encerrar(contrato, moto, cliente)


def _faixa_dados_contrato(contrato):
    proximas = [
        c for c in cobrancas.listar_por_contrato(contrato["id"])
        if c["situacao"] == "aberta" and c["tipo"] == "locacao"
    ]
    proximas.sort(key=lambda c: c["vencimento"])
    proxima = formatar_data(proximas[0]["vencimento"]) if proximas else "—"
    prazo = "Indeterminado" if not contrato.get("data_fim_prevista") else formatar_data(contrato["data_fim_prevista"])
    km_inicial = f"{contrato['km_inicial']:,}".replace(",", ".")
    st.markdown(
        f"""
        <div class="cartao cartao--faixa cartao--faixa-contrato" style="margin-bottom:24px;">
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">valor / período</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['valor_periodo'])}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">caução</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['caucao_valor'])}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">km inicial</span><span class="mono" style="font-size:var(--fs-secundario);">{km_inicial} km</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">prazo</span><span style="font-size:var(--fs-secundario);">{prazo}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">próxima cobrança</span><span class="mono" style="font-size:var(--fs-secundario);">{proxima}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _aba_cobrancas(contrato):
    registros = sorted(cobrancas.listar_por_contrato(contrato["id"]), key=lambda c: c["vencimento"])
    linhas = []
    for c in registros:
        pagamentos = cobrancas.historico_pagamentos(c["id"])
        pago_em = formatar_data(pagamentos[-1]["data_pagamento"]) if pagamentos else None
        if c["situacao"] == "paga":
            situacao_html = selo_situacao("Paga", "paga")
        elif c["situacao"] == "atrasada":
            situacao_html = selo_situacao("Atrasada", "atrasada")
        elif c["situacao"] == "cancelada":
            situacao_html = selo_situacao("Cancelada", "cancelada")
        else:
            situacao_html = selo_situacao("Aberta", "")
        linhas.append(
            [
                c["tipo"].capitalize(),
                f'<span class="mono">{formatar_data(c["vencimento"])}</span>',
                f'<span class="mono">{pago_em}</span>' if pago_em else '<span style="color:var(--texto-3);">—</span>',
                f'<span class="mono">{formatar_moeda(c["valor"])}</span>',
                situacao_html,
            ]
        )
    tabela_html(["Tipo", "Vencimento", "Pago em", "Valor", "Situação"], linhas, legenda="Cobranças do contrato")


def _aba_vistorias(contrato):
    registros = {v["tipo"]: v for v in vistorias.listar_por_contrato(contrato["id"])}
    col_entrega, col_devolucao = st.columns(2, gap="medium")
    for coluna, tipo, titulo in [(col_entrega, "entrega", "Entrega"), (col_devolucao, "devolucao", "Devolução")]:
        vistoria = registros.get(tipo)
        with coluna:
            if not vistoria:
                st.markdown(
                    f"""
                    <div style="background:var(--superficie);border:1px dashed var(--linha);border-radius:var(--raio-sm);padding:18px 22px;
                                display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:10px;height:100%;">
                      <h3 class="rotulo" style="margin:0;font-size:14px;color:var(--texto-2);">{titulo}</h3>
                      <div class="fs-secundario texto-2">Ainda não realizada{" — será registrada no encerramento do contrato." if tipo == "devolucao" else "."}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                continue
            checklist = vistoria.get("checklist") or {}
            avarias = ", ".join(
                nome.replace("_", " ") for nome, estado in checklist.items() if estado == "avaria"
            ) or "Nenhuma"
            st.markdown(
                f"""
                <div class="cartao">
                  <h3 class="rotulo" style="margin:0 0 14px;font-size:14px;">{titulo}</h3>
                  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">data</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(vistoria['data'])}</span></div>
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">km</span><span class="mono" style="font-size:var(--fs-secundario);">{f"{vistoria['km']:,}".replace(",", ".")} km</span></div>
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">combustível</span><span style="font-size:var(--fs-secundario);">{(vistoria.get('nivel_combustivel') or '—').capitalize()}</span></div>
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">avarias</span><span style="font-size:var(--fs-secundario);">{avarias}</span></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _aba_manutencoes(contrato):
    registros = [
        m
        for m in manutencao.listar_manutencoes(contrato["moto_id"])
        if contrato["data_inicio"] <= m["data_entrada"] <= (contrato.get("data_encerramento") or hoje_br().isoformat())
    ]
    registros.sort(key=lambda m: m["data_entrada"], reverse=True)
    linhas = [
        [
            f'<span class="mono">{formatar_data(m["data_entrada"])}</span>',
            m["tipo"].capitalize(),
            m["descricao"],
            f'<span class="mono">{f"{m["km"]:,}".replace(",", ".")} km</span>',
            "Sim" if m.get("cobrar_do_cliente") else '<span style="color:var(--texto-2);">Não</span>',
            f'<span class="mono">{formatar_moeda(m["custo_total"])}</span>',
        ]
        for m in registros
    ]
    tabela_html(["Data", "Tipo", "Descrição", "Km", "Cobrada do cliente", "Custo"], linhas, legenda="Manutenções durante o contrato")
    st.caption("Mostrando apenas manutenções realizadas durante a vigência deste contrato.")


def _exibir_ficha(contrato_id):
    contrato = next((c for c in contratos.listar() if c["id"] == contrato_id), None)
    if not contrato:
        st.warning("Contrato não encontrado.")
        _ir_para_lista()
        return
    moto = next((m for m in motos.listar() if m["id"] == contrato["moto_id"]), None)
    cliente = next((c for c in clientes.listar() if c["id"] == contrato["cliente_id"]), None)
    if not moto or not cliente:
        st.warning("Dados do contrato incompletos.")
        return

    if botao_voltar("contratos", "voltar_contratos"):
        _ir_para_lista()

    _cabecalho_ficha(contrato, moto, cliente)
    st.write("")
    _faixa_dados_contrato(contrato)

    guias = abas("contratos_ficha_abas", ["Cobranças", "Vistorias", "Manutenções"])
    desenho = (_aba_cobrancas, _aba_vistorias, _aba_manutencoes)
    for guia, desenhar in zip(guias, desenho):
        with guia:
            if aba_ativa(guia):
                desenhar(contrato)



def exibir():
    cabecalho("Contratos", exibir_titulo=False)
    with proteger():
        visao = st.session_state.get("contratos_visao", "lista")
        if visao == "wizard":
            _exibir_wizard()
        elif visao == "ficha" and st.session_state.get("contratos_id_selecionado"):
            _exibir_ficha(st.session_state["contratos_id_selecionado"])
        else:
            _exibir_lista()
