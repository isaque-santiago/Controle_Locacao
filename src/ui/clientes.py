"""Clientes: lista e ficha — segue Clientes.dc.html e ClienteFicha.dc.html do mockup."""

from decimal import Decimal
from html import escape

import streamlit as st

from src.services import clientes, contratos, cobrancas, motos, configuracoes
from src.domain import mensagens
from src.domain.entradas import formatar_telefone
from src.domain.valores import hoje_br
from src.domain.cnh_regras import situacao_cnh
from src.ui.componentes import (
    cabecalho,
    cabecalho_pagina,
    estado_vazio,
    vazio_lista,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    tabela_html,
    abrir_ficha_contrato,
    botao_acao,
    botao_voltar,
    cabecalho_ficha,
    cartao_dados,
    cartao_ficha,
    faixa_dados,
    ficha_identidade,
    paineis,
)
from src.ui import feedback
from src.ui.clientes_portal import aba_portal
from src.ui.formularios import (
    campo_cpf,
    campo_email,
    campo_telefone,
    legenda_obrigatorios,
    linha_campos,
    rodape_formulario,
    rotulo_obrigatorio,
)
from src.ui.registros import campo, lista_registros, registro
from src.ui.listas import (
    abas,
    aba_ativa,
    barra_filtros,
    lembrar_registro,
    paginar,
    reiniciar_abas,
    restaurar_posicao,
    rodape_paginacao,
)
from src.ui.formatadores import formatar_data, formatar_moeda, mascarar_cpf

_STATUS_ROTULO = {"ativo": "Ativo", "bloqueado": "Bloqueado", "inativo": "Inativo"}
_OPCOES_FILTRO = [("Todos", "Todos")] + [(chave, _STATUS_ROTULO[chave]) for chave in ("ativo", "bloqueado", "inativo")]


def _html(valor, padrao="—"):
    """Escapa dados cadastrados antes de inseri-los em blocos HTML."""
    if valor is None or valor == "":
        valor = padrao
    # "*" vira entidade: o CPF mascarado (***.123.***-**) virava negrito/itálico no markdown
    return escape(str(valor)).replace("*", "&#42;")


def _ir_para_ficha(cliente_id):
    reiniciar_abas("clientes_ficha_abas")
    lembrar_registro("clientes", cliente_id)
    st.session_state["clientes_visao"] = "ficha"
    st.session_state["clientes_id_selecionado"] = cliente_id
    st.rerun()


def _ir_para_lista():
    st.session_state["clientes_visao"] = "lista"
    st.session_state.pop("clientes_id_selecionado", None)
    st.rerun()


def _iniciais(nome):
    return (nome or "?").strip()[:1].upper()


def _situacao_selo_cliente(status):
    return "ativo_cliente" if status == "ativo" else status


def _identidade_cliente(cliente):
    """Avatar com a inicial + nome, como identidade do cartão da lista."""
    cor_avatar = "var(--chip-fundo)" if cliente["status"] == "ativo" else "var(--avatar-inativo)"
    return (
        '<span class="identidade-linha">'
        f'<span class="avatar avatar--pequeno" style="background:{cor_avatar};">{_html(_iniciais(cliente["nome"]))}</span>'
        f'<span class="fs-secundario">{_html(cliente["nome"])}</span></span>'
    )


def _contrato_ativo_de(cliente_id, contratos_todos=None):
    lista = contratos_todos if contratos_todos is not None else contratos.listar()
    return next((c for c in lista if c["cliente_id"] == cliente_id and c["status"] == "ativo"), None)


# ---------------------------------------------------------------- diálogos --

@st.dialog("Novo cliente")
def _dialog_novo_cliente():
    _formulario_cliente(None)


@st.dialog("Editar dados do cliente")
def _dialog_editar_cliente(cliente):
    _formulario_cliente(cliente)


def _formulario_cliente(cliente):
    cliente = cliente or {}
    with st.form("form_cliente_" + cliente.get("id", "novo")):
        dados = {}
        dados["nome"] = st.text_input(rotulo_obrigatorio("Nome completo"), cliente.get("nome") or "")
        dados["cpf"] = campo_cpf("CPF", cliente.get("cpf"), "cliente_cpf", obrigatorio=True)
        with linha_campos([1, 1], "cliente_telefones") as (col_telefone, col_whatsapp):
            with col_telefone:
                telefone = campo_telefone("Telefone", cliente.get("telefone"), "cliente_telefone")
            with col_whatsapp:
                whatsapp = campo_telefone("WhatsApp", cliente.get("whatsapp"), "cliente_whatsapp")
        dados["email"] = campo_email("E-mail", cliente.get("email"), "cliente_email")
        dados["endereco"] = st.text_input("Endereço", cliente.get("endereco") or "")
        with linha_campos([2, 1], "cliente_cnh") as (col_numero, col_categoria):
            dados["cnh_numero"] = col_numero.text_input("Número da CNH", cliente.get("cnh_numero") or "")
            dados["cnh_categoria"] = col_categoria.text_input("Categoria da CNH", cliente.get("cnh_categoria") or "")
        opcoes = ["ativo", "bloqueado", "inativo"]
        with linha_campos([1, 1], "cliente_validade_status") as (col_validade, col_status):
            with col_validade:
                validade = campo_data("Validade da CNH", cliente.get("cnh_validade"))
            dados["status"] = col_status.selectbox(
                "Status", opcoes, index=opcoes.index(cliente.get("status", "ativo")),
                format_func=_STATUS_ROTULO.get,
            )
        dados["cnh_validade"] = validade.isoformat() if validade else None
        dados["observacoes"] = st.text_area("Observações", cliente.get("observacoes") or "")
        legenda_obrigatorios()
        acao = rodape_formulario("Salvar cliente", "cliente", formulario=True)
        if acao.cancelou:
            st.rerun()
        if acao.confirmou:
            with proteger():
                dados["telefone"] = formatar_telefone(telefone)
                dados["whatsapp"] = formatar_telefone(whatsapp)
                if cliente:
                    clientes.atualizar(cliente["id"], dados)
                else:
                    clientes.criar(dados)
                feedback.concluir(mensagens.cliente_salvo(dados["nome"].strip(), novo=not cliente))


# ------------------------------------------------------------------ lista --

def _exibir_lista():
    registros = clientes.listar()
    config = configuracoes.obter()
    hoje = hoje_br()
    contagem = {
        chave: sum(1 for c in registros if c["status"] == chave)
        for chave in ("ativo", "bloqueado", "inativo")
    }
    contratos_todos = contratos.listar()
    contratos_ativos = {c["cliente_id"]: c["moto_id"] for c in contratos_todos if c["status"] == "ativo"}
    placas = {m["id"]: m["placa"] for m in motos.listar()}

    if cabecalho_pagina(
        "Clientes",
        sub=f"{len(registros)} cliente(s) cadastrado(s)",
        acao={"rotulo": "Novo cliente", "chave": "clientes_novo"},
    ):
        _dialog_novo_cliente()

    filtros = barra_filtros(
        "clientes",
        _OPCOES_FILTRO,
        padrao="Todos",
        contagens={"Todos": len(registros), **contagem},
        busca="Buscar por nome ou CPF",
    )
    busca = filtros.busca.casefold()
    digitos = "".join(ch for ch in busca if ch.isdigit())  # o CPF pode ser digitado com pontos e traço
    filtrados = [
        c
        for c in registros
        if (filtros.valor == "Todos" or c["status"] == filtros.valor)
        and (busca in c["nome"].casefold() or (digitos and digitos in (c.get("cpf") or "")))
    ]
    filtros.resumo(len(filtrados), ("cliente", "clientes"))
    pagina_atual, pagina = paginar("clientes", filtrados)

    with lista_registros("clientes", acoes=1):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhum cliente encontrado.", "Ainda não há clientes cadastrados.", bool(registros), "Novo cliente"),
                unsafe_allow_html=True,
            )
        for cliente in pagina_atual:
            identidade = _identidade_cliente(cliente)
            situacao_cnh_cliente = situacao_cnh(
                _data_iso(cliente.get("cnh_validade")), hoje, config["alerta_cnh_dias"]
            )
            if situacao_cnh_cliente == "sem_cnh":
                cnh = '<span class="fs-secundario texto-3">—</span>'
            else:
                cnh = selo_situacao(formatar_data(cliente["cnh_validade"]), situacao_cnh_cliente)
            moto_id = contratos_ativos.get(cliente["id"])
            campos = [
                campo("CPF", f'<span class="mono fs-secundario texto-2">{_html(mascarar_cpf(cliente.get("cpf") or ""), "")}</span>'),
                campo("WhatsApp", f'<span class="mono fs-secundario">{_html(cliente.get("whatsapp") or cliente.get("telefone"))}</span>'),
                campo("CNH", cnh),
                campo(
                    "Moto atual",
                    chip_placa(placas[moto_id]) if moto_id and moto_id in placas else '<span class="texto-3">—</span>',
                ),
            ]
            with registro(
                "clientes",
                cliente["id"],
                identidade,
                campos,
                selo=selo_situacao(_STATUS_ROTULO[cliente["status"]], _situacao_selo_cliente(cliente["status"])),
            ) as acoes:
                if botao_acao(acoes, "abrir", f"ficha_cli_{cliente['id']}", ajuda=f"Abrir a ficha de {cliente['nome']}"):
                    _ir_para_ficha(cliente["id"])

    rodape_paginacao("clientes", pagina)
    restaurar_posicao("clientes")


def _data_iso(valor):
    from datetime import date

    if not valor:
        return None
    return date.fromisoformat(str(valor)[:10])


# ------------------------------------------------------------------ ficha --

def _card_contrato_ativo(cliente_id):
    contrato = _contrato_ativo_de(cliente_id)
    if not contrato:
        st.markdown(
            cartao_dados("Contrato ativo", '<div class="fs-secundario texto-2">Nenhum contrato ativo para este cliente.</div>'),
            unsafe_allow_html=True,
        )
        return
    moto = next((m for m in motos.listar() if m["id"] == contrato["moto_id"]), None)
    parcelas = [
        c for c in cobrancas.listar_por_contrato(contrato["id"])
        if c["situacao"] == "aberta" and c["tipo"] == "locacao"
    ]
    parcelas.sort(key=lambda c: c["vencimento"])
    proxima = formatar_data(parcelas[0]["vencimento"]) if parcelas else "—"

    acao = {"rotulo": "Ver contrato", "chave": "ver_contrato_cliente", "ajuda": "Abrir o contrato ativo deste cliente"}
    with cartao_ficha("cliente_contrato", "Contrato ativo", acao) as ver_contrato:
        if ver_contrato:
            abrir_ficha_contrato(contrato["id"])
        st.markdown(
            f"""
            <div class="resumo-contrato">
              {chip_placa(moto['placa'], 'grande') if moto else ''}
              <div class="resumo-contrato__texto">
                <div class="resumo-contrato__titulo">{_html(moto['marca'] + ' ' + moto['modelo'] if moto else None)}</div>
                <div class="fs-legenda texto-2">desde {_html(formatar_data(contrato['data_inicio']))} · {_html(contrato['periodicidade'])}</div>
              </div>
            </div>
            <div class="grade-dados grade-dados--compacta campos-linha">
              <div class="campo"><span class="fs-legenda texto-2">valor / período</span><span class="mono fs-secundario">{formatar_moeda(contrato['valor_periodo'])}</span></div>
              <div class="campo"><span class="fs-legenda texto-2">próxima cobrança</span><span class="mono fs-secundario">{proxima}</span></div>
              <div class="campo"><span class="fs-legenda texto-2">caução</span><span class="mono fs-secundario">{formatar_moeda(contrato['caucao_valor'])}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _card_dados_pessoais(cliente):
    """Cartão em largura total: em coluna estreita os valores de 22px (CPF, CNH, e-mail) quebravam no meio."""
    # A categoria vai no rótulo: o número da CNH sozinho cabe em meia largura no celular
    categoria = cliente.get("cnh_categoria")
    rotulo_categoria = f" · cat. {_html(categoria)}" if categoria else ""
    corpo = f"""
      <div class="grade-dados grade-dados--duas">
        <div class="campo"><span class="texto-2">CPF</span><span class="mono">{_html(mascarar_cpf(cliente.get('cpf') or ''), '')}</span></div>
        <div class="campo"><span class="texto-2">CNH{rotulo_categoria}</span><span class="mono">{_html(cliente.get('cnh_numero'))}</span></div>
        <div class="campo"><span class="texto-2">Validade CNH</span><span class="mono">{_html(formatar_data(cliente.get('cnh_validade')))}</span></div>
        <div class="campo"><span class="texto-2">telefone</span><span class="mono">{_html(cliente.get('telefone'))}</span></div>
        <div class="campo campo--largo"><span class="texto-2">e-mail</span><span>{_html(cliente.get('email'))}</span></div>
        <div class="campo campo--largo"><span class="texto-2">endereço</span><span>{_html(cliente.get('endereco'))}</span></div>
      </div>
    """
    st.markdown(cartao_dados("Dados pessoais", corpo), unsafe_allow_html=True)


def _card_situacao_financeira(parcelas, historicos):
    pago = sum(
        (
            Decimal(str(p["valor"])) + Decimal(str(p["multa_juros"]))
            for c in parcelas
            for p in historicos.get(c["id"], [])
        ),
        Decimal(0),
    )
    em_aberto = sum(
        (Decimal(str(c["saldo"])) for c in parcelas if c["situacao"] == "aberta"), Decimal(0)
    )
    atrasado = sum(
        (Decimal(str(c["saldo"])) for c in parcelas if c["situacao"] == "atrasada"), Decimal(0)
    )
    cor_atrasado = "texto-perigo" if atrasado else ""
    corpo = f"""
      <div class="campos-linha pilha-dados">
        <div class="campo"><span class="fs-legenda texto-2">pago no histórico</span><span class="mono fs-destaque texto-sucesso">{formatar_moeda(pago)}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">em aberto</span><span class="mono fs-destaque">{formatar_moeda(em_aberto)}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">atrasado</span><span class="mono fs-destaque {cor_atrasado}">{formatar_moeda(atrasado)}</span></div>
      </div>
    """
    st.markdown(cartao_dados("Situação financeira", corpo), unsafe_allow_html=True)


def _aba_resumo(cliente, parcelas, historicos):
    with paineis("cliente_resumo") as (principal, lateral):
        with principal:
            _card_contrato_ativo(cliente["id"])
        with lateral:
            _card_situacao_financeira(parcelas, historicos)
    _card_dados_pessoais(cliente)


def _aba_contratos(cliente):
    registros = [c for c in contratos.listar() if c["cliente_id"] == cliente["id"]]
    registros.sort(key=lambda c: c["data_inicio"], reverse=True)
    frota = {m["id"]: m for m in motos.listar()}
    with lista_registros("clientes_contratos", acoes=1):
        if not registros:
            st.markdown(
                estado_vazio("Este cliente ainda não tem contratos.", "Os contratos aparecem aqui depois de criados em Contratos.", compacto=True),
                unsafe_allow_html=True,
            )
        for c in registros:
            moto = frota.get(c["moto_id"])
            titulo = (
                f'{chip_placa(moto["placa"])} <span class="fs-secundario">{_html(moto["marca"])} {_html(moto["modelo"])}</span>'
                if moto
                else "—"
            )
            campos = [
                campo("Início", f'<span class="mono fs-secundario">{formatar_data(c["data_inicio"])}</span>'),
                campo(
                    "Fim",
                    f'<span class="mono fs-secundario">{formatar_data(c["data_encerramento"])}</span>'
                    if c["data_encerramento"]
                    else '<span class="texto-3">—</span>',
                ),
                campo("Valor / período", f'<span class="mono fs-secundario">{formatar_moeda(c["valor_periodo"])}</span>'),
            ]
            with registro(
                "clientes_contratos",
                c["id"],
                titulo,
                campos,
                selo=selo_situacao(
                    {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}[c["status"]],
                    c["status"],
                ),
            ) as acoes:
                if botao_acao(
                    acoes,
                    "abrir",
                    f"placa_contrato_{c['id']}",
                    ajuda=f"Abrir o contrato da moto {formatar_placa_simples(moto)}" if moto else "Abrir o contrato",
                ):
                    abrir_ficha_contrato(c["id"])


def _aba_pagamentos(parcelas, historicos):
    parcelas = sorted(
        parcelas,
        key=lambda c: c["vencimento"],
        reverse=True,
    )
    linhas = []
    for c in parcelas:
        pagamentos = historicos.get(c["id"], [])
        ultimo = pagamentos[-1] if pagamentos else None
        multa = sum((Decimal(str(p["multa_juros"])) for p in pagamentos), Decimal(0))
        if c["situacao"] == "atrasada":
            situacao_html = selo_situacao("Atrasada", "atrasada")
        elif c["situacao"] == "aberta" and c["vencimento"] == hoje_br().isoformat():
            situacao_html = selo_situacao("Vence hoje", "proxima")
        elif c["situacao"] == "aberta":
            situacao_html = selo_situacao("Em aberto", "")
        elif c["situacao"] == "paga":
            situacao_html = selo_situacao("Paga", "paga")
        else:
            situacao_html = selo_situacao("Cancelada", "cancelada")
        linhas.append(
            [
                f'<span class="mono">{formatar_data(c["vencimento"])}</span>',
                _html(c["tipo"].capitalize()),
                f'<span class="mono">{formatar_data(ultimo["data_pagamento"])}</span>' if ultimo else '<span class="texto-3">—</span>',
                _html(ultimo["forma"].capitalize()) if ultimo else '<span class="texto-3">—</span>',
                f'<span class="mono">{formatar_moeda(multa)}</span>' if multa else '<span class="texto-3">—</span>',
                f'<span class="mono">{formatar_moeda(c["valor"])}</span>',
                situacao_html,
            ]
        )
    tabela_html(
        ["Vencimento", "Tipo", "Pago em", "Forma", "Multa/juros", "Valor", "Situação"],
        linhas,
        legenda="Pagamentos do cliente",
    )


def _exibir_ficha(cliente_id):
    cliente = clientes.obter(cliente_id)
    if not cliente:
        st.warning("Cliente não encontrado.")
        _ir_para_lista()
        return

    if botao_voltar("clientes", "voltar_clientes"):
        _ir_para_lista()

    contrato = _contrato_ativo_de(cliente_id)
    if cliente["status"] == "ativo" and contrato:
        moto = next((m for m in motos.listar() if m["id"] == contrato["moto_id"]), None)
        linha_status = f"Ativo · alugando {formatar_placa_simples(moto)} desde {formatar_data(contrato['data_inicio'])}"
    else:
        linha_status = _STATUS_ROTULO[cliente["status"]]

    avatar = f'<div class="avatar-ficha{"" if cliente["status"] == "ativo" else " avatar-ficha--inativo"}">{_html(_iniciais(cliente["nome"]))}</div>'
    cliques = cabecalho_ficha(
        ficha_identidade(
            _html(cliente["nome"]),
            selo=selo_situacao(linha_status, _situacao_selo_cliente(cliente["status"])),
            marca=avatar,
        ),
        [{"rotulo": "Editar", "chave": "editar_cliente_ficha", "ajuda": "Editar os dados do cliente"}],
    )
    if cliques["editar_cliente_ficha"]:
        _dialog_editar_cliente(cliente)

    config = configuracoes.obter()
    situacao_cnh_cliente = situacao_cnh(_data_iso(cliente.get("cnh_validade")), hoje_br(), config["alerta_cnh_dias"])
    if situacao_cnh_cliente == "sem_cnh":
        cnh_html = "Sem CNH cadastrada"
        cnh_tom = "texto-3"
    else:
        cnh_html = selo_situacao(
            f"categoria {cliente.get('cnh_categoria') or '—'} · válida até {formatar_data(cliente['cnh_validade'])}",
            situacao_cnh_cliente,
        )
        cnh_tom = None
    faixa_dados(
        [
            ("CPF", f'<span class="mono">{_html(mascarar_cpf(cliente.get("cpf") or ""), "")}</span>'),
            ("WhatsApp", f'<span class="mono">{_html(cliente.get("whatsapp") or cliente.get("telefone"))}</span>'),
            ("CNH", cnh_html, cnh_tom),
            ("E-mail", _html(cliente.get("email"))),
        ]
    )

    parcelas = [c for c in cobrancas.listar() if c["cliente_id"] == cliente_id]
    historicos = cobrancas.historicos_pagamentos([c["id"] for c in parcelas])

    guias = abas("clientes_ficha_abas", ["Resumo", "Contratos", "Pagamentos", "Portal"])
    desenho = (
        lambda: _aba_resumo(cliente, parcelas, historicos),
        lambda: _aba_contratos(cliente),
        lambda: _aba_pagamentos(parcelas, historicos),
        lambda: aba_portal(cliente),
    )
    for guia, desenhar in zip(guias, desenho):
        with guia:
            if aba_ativa(guia):
                desenhar()


def formatar_placa_simples(moto):
    from src.ui.formatadores import formatar_placa

    return formatar_placa(moto["placa"]) if moto else "—"


def exibir():
    cabecalho("Clientes", exibir_titulo=False)
    with proteger(nova_tentativa=True):
        visao = st.session_state.get("clientes_visao", "lista")
        if visao == "ficha" and st.session_state.get("clientes_id_selecionado"):
            _exibir_ficha(st.session_state["clientes_id_selecionado"])
        else:
            _exibir_lista()
