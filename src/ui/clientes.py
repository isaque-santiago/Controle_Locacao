"""Clientes: lista e ficha — segue Clientes.dc.html e ClienteFicha.dc.html do mockup."""

from decimal import Decimal
from html import escape

import streamlit as st

from src.services import clientes, contratos, cobrancas, motos, configuracoes
from src.domain.valores import hoje_br
from src.domain.cnh_regras import situacao_cnh
from src.ui.componentes import (
    cabecalho,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    tabela_html,
    abrir_ficha_contrato,
)
from src.ui.formatadores import formatar_data, formatar_moeda, mascarar_cpf

_STATUS_ROTULO = {"ativo": "Ativo", "bloqueado": "Bloqueado", "inativo": "Inativo"}
_FILTROS = ["Todos", "ativo", "bloqueado", "inativo"]


def _html(valor, padrao="—"):
    """Escapa dados cadastrados antes de inseri-los em blocos HTML."""
    if valor is None or valor == "":
        valor = padrao
    return escape(str(valor))


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _ir_para_ficha(cliente_id):
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
        for campo, titulo in [
            ("nome", "Nome completo"),
            ("cpf", "CPF"),
            ("telefone", "Telefone"),
            ("whatsapp", "WhatsApp"),
            ("email", "E-mail"),
            ("endereco", "Endereço"),
            ("cnh_numero", "Número da CNH"),
            ("cnh_categoria", "Categoria da CNH"),
        ]:
            dados[campo] = st.text_input(titulo, cliente.get(campo) or "")
        validade = campo_data("Validade da CNH", cliente.get("cnh_validade"))
        dados["cnh_validade"] = validade.isoformat() if validade else None
        opcoes = ["ativo", "bloqueado", "inativo"]
        dados["status"] = st.selectbox(
            "Status", opcoes, index=opcoes.index(cliente.get("status", "ativo"))
        )
        dados["observacoes"] = st.text_area("Observações", cliente.get("observacoes") or "")
        if st.form_submit_button("Salvar cliente", type="primary", use_container_width=True):
            if cliente:
                clientes.atualizar(cliente["id"], dados)
            else:
                clientes.criar(dados)
            _salvo()


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

    col_titulo, col_botao = st.columns([5, 1], vertical_alignment="center")
    col_titulo.markdown(
        f"""
        <h1 class="rotulo pagina-titulo">Clientes</h1>
        <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">{len(registros)} cliente(s) cadastrado(s)</div>
        """,
        unsafe_allow_html=True,
    )
    with col_botao:
        if st.button("+ Novo cliente", type="primary", use_container_width=True):
            _dialog_novo_cliente()

    st.write("")
    filtro_atual = st.session_state.get("clientes_filtro", "Todos")
    col_pills, col_busca = st.columns([3, 1.3])
    with col_pills:
        with st.container(key="clientes_filtros"):
            pills = st.columns(len(_FILTROS))
            rotulos_pill = ["Todos"] + [_STATUS_ROTULO[f] for f in _FILTROS[1:]]
            for coluna, valor, rotulo in zip(pills, _FILTROS, rotulos_pill):
                total_pill = len(registros) if valor == "Todos" else contagem.get(valor, 0)
                if coluna.button(
                    f"{rotulo} · {total_pill}",
                    key=f"pill_cli_{valor}",
                    type="primary" if filtro_atual == valor else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["clientes_filtro"] = valor
                    st.rerun()
    with col_busca:
        busca = st.text_input(
            "Buscar", placeholder="Buscar por nome ou CPF", label_visibility="collapsed"
        )

    busca_normalizada = busca.casefold()
    filtrados = [
        c
        for c in registros
        if (filtro_atual == "Todos" or c["status"] == filtro_atual)
        and (busca_normalizada in c["nome"].casefold() or busca_normalizada in (c.get("cpf") or ""))
    ]

    st.write("")
    pagina_chave = "clientes_pagina"
    por_pagina = 6
    total_paginas = max(1, -(-len(filtrados) // por_pagina))
    pagina = min(st.session_state.get(pagina_chave, 1), total_paginas)
    inicio = (pagina - 1) * por_pagina
    pagina_atual = filtrados[inicio : inicio + por_pagina]

    with st.container(key="clientes_card_lista"):
        cab = st.columns([1.6, 1.3, 1.3, 1.2, 1.1, 1.1, 0.4], vertical_alignment="center")
        for coluna, rotulo in zip(cab, ["Nome", "CPF", "WhatsApp", "CNH", "Status", "Moto atual", ""]):
            coluna.markdown(
                f'<span class="fs-secundario texto-2">{rotulo}</span>',
                unsafe_allow_html=True,
            )
        if not pagina_atual:
            st.markdown(
                '<div class="vazio vazio--linha">Nenhum cliente encontrado.</div>',
                unsafe_allow_html=True,
            )
        for cliente in pagina_atual:
            linha = st.columns([1.6, 1.3, 1.3, 1.2, 1.1, 1.1, 0.4], vertical_alignment="center")
            cor_avatar = "var(--chip-fundo)" if cliente["status"] == "ativo" else "var(--avatar-inativo)"
            linha[0].markdown(
                f"""
                <div style="display:flex;align-items:center;gap:10px;">
                  <div style="width:26px;height:26px;border-radius:50%;background:{cor_avatar};color:var(--chip-texto);
                              display:flex;align-items:center;justify-content:center;font-size:var(--fs-legenda);
                              font-weight:600;flex-shrink:0;">{_html(_iniciais(cliente['nome']))}</div>
                  <span style="font-size:var(--fs-secundario);">{_html(cliente['nome'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            linha[1].markdown(
                f'<span class="mono" class="fs-secundario texto-2">{_html(mascarar_cpf(cliente.get("cpf") or ""), "")}</span>',
                unsafe_allow_html=True,
            )
            linha[2].markdown(
                f'<span class="mono" style="font-size:var(--fs-secundario);">{_html(cliente.get("whatsapp") or cliente.get("telefone"))}</span>',
                unsafe_allow_html=True,
            )
            situacao_cnh_cliente = situacao_cnh(
                _data_iso(cliente.get("cnh_validade")), hoje, config["alerta_cnh_dias"]
            )
            if situacao_cnh_cliente == "sem_cnh":
                linha[3].markdown('<span style="font-size:var(--fs-secundario);color:var(--texto-3);">—</span>', unsafe_allow_html=True)
            else:
                linha[3].markdown(
                    selo_situacao(formatar_data(cliente["cnh_validade"]), situacao_cnh_cliente),
                    unsafe_allow_html=True,
                )
            linha[4].markdown(
                selo_situacao(_STATUS_ROTULO[cliente["status"]], _situacao_selo_cliente(cliente["status"])),
                unsafe_allow_html=True,
            )
            moto_id = contratos_ativos.get(cliente["id"])
            linha[5].markdown(
                chip_placa(placas[moto_id]) if moto_id and moto_id in placas else '<span style="color:var(--texto-3);">—</span>',
                unsafe_allow_html=True,
            )
            if linha[6].button("→", key=f"ficha_cli_{cliente['id']}", help="Ver ficha"):
                _ir_para_ficha(cliente["id"])

    if total_paginas > 1:
        st.caption(f"Mostrando {len(pagina_atual)} de {len(filtrados)} · página {pagina} de {total_paginas}")
        col_ant, col_prox = st.columns(2)
        if col_ant.button("‹ Anterior", disabled=pagina <= 1, key="cli_ant"):
            st.session_state[pagina_chave] = pagina - 1
            st.rerun()
        if col_prox.button("Próxima ›", disabled=pagina >= total_paginas, key="cli_prox"):
            st.session_state[pagina_chave] = pagina + 1
            st.rerun()


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
            """
            <div class="cartao">
              <h3 class="rotulo" style="margin:0 0 6px;font-size:14px;">Contrato ativo</h3>
              <div class="fs-secundario texto-2">Nenhum contrato ativo para este cliente.</div>
            </div>
            """,
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

    # O botão vai no cabeçalho do cartão, à direita do título (não solto abaixo dele)
    with st.container(key="cliente_contrato_ativo"):
        titulo, acao = st.columns([3, 1], vertical_alignment="center")
        titulo.markdown(
            '<h3 class="rotulo" style="margin:0;font-size:14px;">Contrato ativo</h3>',
            unsafe_allow_html=True,
        )
        with acao:
            if st.button("Ver contrato →", key="ver_contrato_cliente"):
                abrir_ficha_contrato(contrato["id"])
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
              {chip_placa(moto['placa'], 'grande') if moto else ''}
              <div>
                <div style="font-size:14px;font-weight:500;">{_html(moto['marca'] + ' ' + moto['modelo'] if moto else None)}</div>
                <div style="font-size:var(--fs-legenda);color:var(--texto-2);">desde {_html(formatar_data(contrato['data_inicio']))} · {_html(contrato['periodicidade'])}</div>
              </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;">
              <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">valor / período</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['valor_periodo'])}</span></div>
              <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">próxima cobrança</span><span class="mono" style="font-size:var(--fs-secundario);">{proxima}</span></div>
              <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">caução</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['caucao_valor'])}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _card_dados_pessoais(cliente):
    """Cartão em largura total: em coluna estreita os valores de 22px (CPF, CNH, e-mail) quebravam no meio."""
    st.markdown(
        f"""
        <div class="cartao">
          <h3 class="rotulo" style="margin:0 0 14px;font-size:14px;">Dados pessoais</h3>
          <div class="grade-dados">
            <div class="campo"><span class="texto-2">CPF</span><span class="mono">{_html(mascarar_cpf(cliente.get('cpf') or ''), '')}</span></div>
            <div class="campo"><span class="texto-2">CNH</span><span class="mono">{_html(cliente.get('cnh_numero'))} · cat. {_html(cliente.get('cnh_categoria'))}</span></div>
            <div class="campo"><span class="texto-2">Validade CNH</span><span class="mono">{_html(formatar_data(cliente.get('cnh_validade')))}</span></div>
            <div class="campo"><span class="texto-2">telefone</span><span class="mono">{_html(cliente.get('telefone'))}</span></div>
            <div class="campo"><span class="texto-2">e-mail</span><span>{_html(cliente.get('email'))}</span></div>
            <div class="campo"><span class="texto-2">endereço</span><span>{_html(cliente.get('endereco'))}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    st.markdown(
        f"""
        <div class="cartao" style="height:100%;">
          <h3 class="rotulo" style="margin:0 0 14px;font-size:14px;">Situação financeira</h3>
          <div style="display:flex;flex-direction:column;gap:14px;">
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">pago no histórico</span><span class="mono" style="font-size:18px;color:var(--sucesso-texto);">{formatar_moeda(pago)}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">em aberto</span><span class="mono" style="font-size:18px;">{formatar_moeda(em_aberto)}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">atrasado</span><span class="mono" style="font-size:18px;color:{'var(--perigo-texto)' if atrasado else 'var(--texto)'};">{formatar_moeda(atrasado)}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _aba_resumo(cliente, parcelas, historicos):
    esquerda, direita = st.columns([1.5, 1], gap="medium")
    with esquerda:
        _card_contrato_ativo(cliente["id"])
    with direita:
        _card_situacao_financeira(parcelas, historicos)
    st.write("")
    _card_dados_pessoais(cliente)


def _aba_contratos(cliente):
    registros = [c for c in contratos.listar() if c["cliente_id"] == cliente["id"]]
    registros.sort(key=lambda c: c["data_inicio"], reverse=True)
    frota = {m["id"]: m for m in motos.listar()}
    larguras = [2, 1, 1, 1, 1]
    with st.container(key="clientes_card_lista"):
        cab = st.columns(larguras, vertical_alignment="center")
        for coluna, rotulo in zip(cab, ["Moto", "Início", "Fim", "Status", "Valor / período"]):
            coluna.markdown(
                f'<span class="fs-secundario texto-2">{rotulo}</span>',
                unsafe_allow_html=True,
            )
        if not registros:
            st.markdown(
                '<div class="vazio vazio--linha">Nenhum registro encontrado.</div>',
                unsafe_allow_html=True,
            )
        for c in registros:
            moto = frota.get(c["moto_id"])
            linha = st.columns(larguras, vertical_alignment="center")
            if moto:
                col_placa, col_modelo = linha[0].columns([1, 1.6], vertical_alignment="center")
                if col_placa.button(
                    formatar_placa_simples(moto),
                    key=f"placa_contrato_{c['id']}",
                    help="Abrir contrato",
                ):
                    abrir_ficha_contrato(c["id"])
                col_modelo.markdown(
                    f'<span style="font-size:var(--fs-secundario);">{_html(moto["marca"])} {_html(moto["modelo"])}</span>',
                    unsafe_allow_html=True,
                )
            else:
                linha[0].markdown("—")
            linha[1].markdown(
                f'<span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(c["data_inicio"])}</span>',
                unsafe_allow_html=True,
            )
            linha[2].markdown(
                f'<span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(c["data_encerramento"])}</span>'
                if c["data_encerramento"]
                else '<span style="color:var(--texto-3);">—</span>',
                unsafe_allow_html=True,
            )
            linha[3].markdown(
                selo_situacao(
                    {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}[c["status"]],
                    c["status"],
                ),
                unsafe_allow_html=True,
            )
            linha[4].markdown(
                f'<span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(c["valor_periodo"])}</span>',
                unsafe_allow_html=True,
            )


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
                f'<span class="mono">{formatar_data(ultimo["data_pagamento"])}</span>' if ultimo else '<span style="color:var(--texto-3);">—</span>',
                _html(ultimo["forma"].capitalize()) if ultimo else '<span style="color:var(--texto-3);">—</span>',
                f'<span class="mono">{formatar_moeda(multa)}</span>' if multa else '<span style="color:var(--texto-3);">—</span>',
                f'<span class="mono">{formatar_moeda(c["valor"])}</span>',
                situacao_html,
            ]
        )
    tabela_html(
        ["Vencimento", "Tipo", "Pago em", "Forma", "Multa/juros", "Valor", "Situação"],
        linhas,
    )


def _exibir_ficha(cliente_id):
    cliente = clientes.obter(cliente_id)
    if not cliente:
        st.warning("Cliente não encontrado.")
        _ir_para_lista()
        return

    if st.button("‹ Clientes", key="voltar_clientes"):
        _ir_para_lista()

    contrato = _contrato_ativo_de(cliente_id)
    if cliente["status"] == "ativo" and contrato:
        moto = next((m for m in motos.listar() if m["id"] == contrato["moto_id"]), None)
        linha_status = f"Ativo · alugando {formatar_placa_simples(moto)} desde {formatar_data(contrato['data_inicio'])}"
    else:
        linha_status = _STATUS_ROTULO[cliente["status"]]

    col_cab, col_acoes = st.columns([3, 1], vertical_alignment="center")
    with col_cab:
        cor_avatar = "var(--chip-fundo)" if cliente["status"] == "ativo" else "var(--avatar-inativo)"
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:16px;">
              <div style="width:48px;height:48px;border-radius:50%;background:{cor_avatar};color:var(--chip-texto);
                          display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:600;flex-shrink:0;">{_html(_iniciais(cliente['nome']))}</div>
              <div>
                <h1 class="rotulo" style="margin:0;font-size:24px;">{_html(cliente['nome'])}</h1>
                <div style="font-size:var(--fs-secundario);margin-top:3px;">
                  {selo_situacao(linha_status, _situacao_selo_cliente(cliente["status"]))}
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_acoes:
        if st.button("Editar", use_container_width=True):
            _dialog_editar_cliente(cliente)

    st.write("")
    config = configuracoes.obter()
    situacao_cnh_cliente = situacao_cnh(_data_iso(cliente.get("cnh_validade")), hoje_br(), config["alerta_cnh_dias"])
    cnh_html = (
        f'<span style="font-size:var(--fs-secundario);color:var(--texto-3);">Sem CNH cadastrada</span>'
        if situacao_cnh_cliente == "sem_cnh"
        else selo_situacao(
            f"categoria {cliente.get('cnh_categoria') or '—'} · válida até {formatar_data(cliente['cnh_validade'])}",
            situacao_cnh_cliente,
        )
    )
    st.markdown(
        f"""
        <div class="cartao cartao--faixa" style="margin-bottom:20px;">
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">CPF</span><span class="mono" style="font-size:var(--fs-secundario);">{_html(mascarar_cpf(cliente.get('cpf') or ''), '')}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">whatsapp</span><span class="mono" style="font-size:var(--fs-secundario);">{_html(cliente.get('whatsapp') or cliente.get('telefone'))}</span>
          </div>
          <div style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);display:flex;flex-direction:column;gap:4px;justify-content:center;">
            <span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">CNH</span>
            {cnh_html}
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">e-mail</span><span style="font-size:var(--fs-secundario);">{_html(cliente.get('email'))}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    parcelas = [c for c in cobrancas.listar() if c["cliente_id"] == cliente_id]
    historicos = cobrancas.historicos_pagamentos([c["id"] for c in parcelas])

    abas = st.tabs(["Resumo", "Contratos", "Pagamentos"])
    with abas[0]:
        _aba_resumo(cliente, parcelas, historicos)
    with abas[1]:
        _aba_contratos(cliente)
    with abas[2]:
        _aba_pagamentos(parcelas, historicos)


def formatar_placa_simples(moto):
    from src.ui.formatadores import formatar_placa

    return formatar_placa(moto["placa"]) if moto else "—"


def exibir():
    cabecalho("Clientes", exibir_titulo=False)
    with proteger():
        visao = st.session_state.get("clientes_visao", "lista")
        if visao == "ficha" and st.session_state.get("clientes_id_selecionado"):
            _exibir_ficha(st.session_state["clientes_id_selecionado"])
        else:
            _exibir_lista()
