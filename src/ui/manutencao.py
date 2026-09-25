"""Manutenção: alertas, histórico e catálogo — segue Manutencao.dc.html do mockup."""

from decimal import Decimal

import pandas as pd
import streamlit as st

from src.services import manutencao, motos, alertas
from src.domain.valores import hoje_br, decimal_br
from src.domain.manutencao_regras import preparar_itens_adicionais
from src.ui.componentes import (
    cabecalho,
    proteger,
    selecionar,
    chip_placa,
    selo_situacao,
    tabela_html,
)
from src.ui.formatadores import formatar_data, formatar_moeda

_SITUACAO_ROTULO = {"vencida": "Vencida", "proxima": "Próxima"}
_FILTROS_ALERTA = [("todas", "Todas"), ("vencida", "Vencidas"), ("proxima", "Próximas")]
_FILTROS_TIPO = [("todas", "Todas"), ("preventiva", "Preventiva"), ("corretiva", "Corretiva")]
_STATUS_ROTULO = {"aberta": "Aberta", "concluida": "Concluída", "cancelada": "Cancelada"}
# "aberta" é estado operacional (sem tinta); concluída usa o verde de "ok".
_STATUS_SELO = {"aberta": "aberta", "concluida": "ok", "cancelada": "cancelada"}
_POR_PAGINA = 8
_PREFIXO_REGISTRO = "manreg_"


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _km(valor):
    return f"{int(valor):,} km".replace(",", ".") if valor is not None else "—"


def _mono(texto, estilo=""):
    return f'<span class="mono" style="font-size:var(--fs-secundario);{estilo}">{texto}</span>'


def _texto(texto, estilo=""):
    return f'<span style="font-size:var(--fs-secundario);{estilo}">{texto}</span>'


def _cabecalho_tabela(colunas, rotulos):
    for coluna, rotulo in zip(colunas, rotulos):
        coluna.markdown(
            f'<span class="fs-secundario texto-2">{rotulo}</span>',
            unsafe_allow_html=True,
        )


def _pills(chave, opcoes, contagens, padrao="todas"):
    """Filtros em pílula (mesmo padrão de Motos/Clientes/Contratos). Devolve o valor ativo."""
    atual = st.session_state.get(f"manutencao_{chave}", padrao)
    with st.container(key=f"manutencao_filtros_{chave}"):
        colunas = st.columns(len(opcoes))
        for coluna, (valor, rotulo) in zip(colunas, opcoes):
            total = contagens.get(valor)
            texto = f"{rotulo} · {total}" if total is not None else rotulo
            if coluna.button(
                texto,
                key=f"pill_man_{chave}_{valor}",
                type="primary" if atual == valor else "secondary",
                use_container_width=True,
            ):
                st.session_state[f"manutencao_{chave}"] = valor
                st.session_state[f"manutencao_pagina_{chave}"] = 1
                st.rerun()
    return atual


def _paginar(chave, registros):
    total_paginas = max(1, -(-len(registros) // _POR_PAGINA))
    pagina = min(st.session_state.get(f"manutencao_pagina_{chave}", 1), total_paginas)
    inicio = (pagina - 1) * _POR_PAGINA
    return registros[inicio : inicio + _POR_PAGINA], pagina, total_paginas


def _rodape_paginacao(chave, exibidos, total, pagina, total_paginas):
    if total_paginas <= 1:
        return
    st.caption(f"Mostrando {exibidos} de {total} · página {pagina} de {total_paginas}")
    anterior, proxima = st.columns(2)
    if anterior.button("‹ Anterior", disabled=pagina <= 1, key=f"man_ant_{chave}"):
        st.session_state[f"manutencao_pagina_{chave}"] = pagina - 1
        st.rerun()
    if proxima.button("Próxima ›", disabled=pagina >= total_paginas, key=f"man_prox_{chave}"):
        st.session_state[f"manutencao_pagina_{chave}"] = pagina + 1
        st.rerun()


# ---------------------------------------------------------------- diálogos --

def _valor_tolerante(texto, positivo=False):
    """Valor para a prévia ao vivo: entrada inválida conta como zero (o erro
    aparece só ao salvar, via decimal_br)."""
    try:
        return decimal_br(texto, positivo=positivo)
    except ValueError:
        return Decimal("0.00")


def _limpar_registro():
    for chave in [c for c in st.session_state if str(c).startswith(_PREFIXO_REGISTRO)]:
        del st.session_state[chave]


@st.dialog("Registrar manutenção", width="large")
def _dialog_registrar():
    frota = [m for m in motos.listar() if m["status"] != "inativa"]
    itens = [i for i in manutencao.listar_catalogo() if i["ativo"]]
    if not frota:
        st.info("Cadastre uma moto ativa antes de registrar manutenções.")
        return

    moto = selecionar(
        "Moto",
        frota,
        lambda m: f"{m['placa']} · {m['marca']} {m['modelo']}",
        _PREFIXO_REGISTRO + "moto",
    )
    col_tipo, col_status = st.columns(2)
    tipo = col_tipo.radio(
        "Tipo", ["Preventiva", "Corretiva"], horizontal=True, key=_PREFIXO_REGISTRO + "tipo"
    ).lower()
    status_rotulo = col_status.radio(
        "Status", ["Concluída", "Aberta"], horizontal=True, key=_PREFIXO_REGISTRO + "status"
    )
    concluida = status_rotulo == "Concluída"

    col_entrada, col_saida, col_km = st.columns(3)
    entrada = col_entrada.date_input(
        "Data de entrada", hoje_br(), format="DD/MM/YYYY", key=_PREFIXO_REGISTRO + "entrada"
    )
    saida = col_saida.date_input(
        "Data de saída",
        entrada,
        min_value=entrada,
        format="DD/MM/YYYY",
        disabled=not concluida,
        key=_PREFIXO_REGISTRO + "saida",
    )
    km = col_km.number_input(
        "Km",
        min_value=moto["km_atual"],
        value=moto["km_atual"],
        step=1,
        key=f"{_PREFIXO_REGISTRO}km_{moto['id']}",
    )
    oficina = st.text_input("Oficina", key=_PREFIXO_REGISTRO + "oficina")
    descricao = st.text_area("Descrição", height=80, key=_PREFIXO_REGISTRO + "descricao")

    escolhidos = st.multiselect(
        "Itens do plano substituídos ou revisados",
        [i["id"] for i in itens],
        format_func=lambda id: next(i["nome"] for i in itens if i["id"] == id),
        key=_PREFIXO_REGISTRO + "itens",
        help="Itens marcados aqui zeram o contador do plano da moto.",
    )
    linhas_plano = []
    if escolhidos:
        cab = st.columns([3, 1, 1.4, 1.4])
        _cabecalho_tabela(cab, ["Item", "Qtd.", "Unitário (R$)", "Subtotal"])
    for id in escolhidos:
        item = next(i for i in itens if i["id"] == id)
        c_nome, c_qtd, c_valor, c_sub = st.columns([3, 1, 1.4, 1.4], vertical_alignment="center")
        c_nome.markdown(
            _texto(item["nome"]) + ' <span style="font-size:var(--fs-legenda);color:var(--texto-3);">(plano)</span>',
            unsafe_allow_html=True,
        )
        qtd = c_qtd.text_input("Quantidade", "1", key=f"{_PREFIXO_REGISTRO}qtd_{id}", label_visibility="collapsed")
        valor = c_valor.text_input("Valor unitário", "0", key=f"{_PREFIXO_REGISTRO}valor_{id}", label_visibility="collapsed")
        subtotal = _valor_tolerante(qtd, positivo=True) * _valor_tolerante(valor)
        c_sub.markdown(_mono(formatar_moeda(subtotal)), unsafe_allow_html=True)
        linhas_plano.append((item, qtd, valor, subtotal))

    st.caption("Outras peças ou serviços")
    adicionais = st.data_editor(
        pd.DataFrame([{"descricao": "", "quantidade": "1", "valor_unitario": "0"}]),
        key=_PREFIXO_REGISTRO + "adicionais",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "descricao": st.column_config.TextColumn("Descrição", required=False),
            "quantidade": st.column_config.TextColumn("Quantidade", required=False),
            "valor_unitario": st.column_config.TextColumn("Valor unitário (R$)", required=False),
        },
    )
    registros_adicionais = adicionais.to_dict("records")

    col_mao, col_pecas, col_total = st.columns(3, vertical_alignment="bottom")
    mao_obra = col_mao.text_input("Custo de mão de obra (R$)", "0", key=_PREFIXO_REGISTRO + "mao_obra")
    pecas = sum((s for *_, s in linhas_plano), Decimal("0.00")) + sum(
        (
            _valor_tolerante(str(r.get("quantidade") or "1"), positivo=True)
            * _valor_tolerante(str(r.get("valor_unitario") or "0"))
            for r in registros_adicionais
            if str(r.get("descricao") or "").strip()
        ),
        Decimal("0.00"),
    )
    total = pecas + _valor_tolerante(mao_obra)
    col_pecas.markdown(
        f'<div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">custo de peças</span>'
        f'{_mono(formatar_moeda(pecas), "font-size:15px;")}</div>',
        unsafe_allow_html=True,
    )
    col_total.markdown(
        f'<div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">custo total</span>'
        f'{_mono(formatar_moeda(total), "font-size:18px;font-weight:600;")}</div>',
        unsafe_allow_html=True,
    )
    cobrar = st.checkbox(
        "Cobrar do cliente (gera cobrança de dano no contrato vigente)",
        key=_PREFIXO_REGISTRO + "cobrar",
    )

    col_cancelar, col_salvar = st.columns(2)
    if col_cancelar.button("Cancelar", use_container_width=True, key=_PREFIXO_REGISTRO + "cancelar"):
        _limpar_registro()
        st.rerun()
    if col_salvar.button(
        "Salvar manutenção", type="primary", use_container_width=True, key=_PREFIXO_REGISTRO + "salvar"
    ):
        with proteger():
            if not descricao.strip():
                raise ValueError("Informe a descrição do serviço.")
            lista = [
                {
                    "item_id": item["id"],
                    "descricao": item["nome"],
                    "quantidade": decimal_br(qtd, positivo=True),
                    "valor_unitario": decimal_br(valor),
                }
                for item, qtd, valor, _ in linhas_plano
            ]
            lista.extend(preparar_itens_adicionais(registros_adicionais))
            manutencao.registrar_manutencao(
                moto["id"],
                tipo,
                entrada,
                km,
                descricao,
                status="concluida" if concluida else "aberta",
                data_saida=saida if concluida else None,
                oficina=oficina,
                custo_mao_obra=decimal_br(mao_obra),
                cobrar_do_cliente=cobrar,
                itens=lista,
            )
            _limpar_registro()
            _salvo("Manutenção registrada.")


@st.dialog("Atualizar manutenção aberta")
def _dialog_concluir(registro, moto):
    st.markdown(chip_placa(moto["placa"]), unsafe_allow_html=True)
    st.write(f"{formatar_data(registro['data_entrada'])} · {registro['descricao']}")
    piso = max(moto["km_atual"], registro["km"])
    with st.form("form_concluir_" + registro["id"]):
        data_saida = st.date_input("Data de conclusão", hoje_br(), format="DD/MM/YYYY")
        km = st.number_input("Km na conclusão", min_value=piso, value=piso, step=1)
        acao = st.radio(
            "Ação",
            ["concluida", "cancelada"],
            format_func=_STATUS_ROTULO.get,
            horizontal=True,
        )
        if st.form_submit_button("Atualizar manutenção", type="primary", use_container_width=True):
            with proteger():
                manutencao.finalizar(registro["id"], acao, data_saida, km)
                _salvo("Manutenção atualizada.")


@st.dialog("Item do catálogo")
def _dialog_item(item):
    with st.form("form_catalogo_" + item.get("id", "novo")):
        nome = st.text_input("Nome", item.get("nome", ""))
        col_km, col_dias = st.columns(2)
        km = col_km.number_input(
            "Intervalo km (0 sem limite)", min_value=0, value=item.get("intervalo_km") or 0, step=1
        )
        dias = col_dias.number_input(
            "Intervalo dias (0 sem limite)", min_value=0, value=item.get("intervalo_dias") or 0, step=1
        )
        ativo = st.checkbox("Ativo", item.get("ativo", True))
        if st.form_submit_button("Salvar item", type="primary", use_container_width=True):
            with proteger():
                if not nome.strip() or not (km or dias):
                    raise ValueError("Informe o nome e pelo menos um intervalo.")
                dados = {
                    "nome": nome,
                    "intervalo_km": km or None,
                    "intervalo_dias": dias or None,
                    "ativo": ativo,
                }
                if item:
                    manutencao.atualizar_item_catalogo(item["id"], dados)
                else:
                    manutencao.criar_item_catalogo(dados)
                _salvo("Item salvo.")


# ------------------------------------------------------------------ abas --

def _restante(alerta):
    partes = []
    negativo = False
    if alerta.get("km_restantes") is not None:
        partes.append(_km(alerta["km_restantes"]))
        negativo = negativo or alerta["km_restantes"] < 0
    if alerta.get("dias_restantes") is not None:
        partes.append(f"{alerta['dias_restantes']} dias")
        negativo = negativo or alerta["dias_restantes"] < 0
    cor = "color:var(--perigo-texto);" if negativo else ""
    return f'<span class="mono" style="{cor}">{" / ".join(partes) or "—"}</span>'


def _aba_alertas(pendentes):
    contagem = {
        "todas": len(pendentes),
        "vencida": sum(a["situacao"] == "vencida" for a in pendentes),
        "proxima": sum(a["situacao"] == "proxima" for a in pendentes),
    }
    filtro = _pills("filtro_alerta", _FILTROS_ALERTA, contagem)
    visiveis = [a for a in pendentes if filtro == "todas" or a["situacao"] == filtro]
    visiveis.sort(
        key=lambda a: (
            a["situacao"] != "vencida",
            a["km_restantes"] if a.get("km_restantes") is not None else float("inf"),
        )
    )
    st.write("")
    linhas = []
    for a in visiveis:
        proxima = " / ".join(
            filter(
                None,
                [
                    _km(a["proxima_km"]) if a.get("proxima_km") is not None else None,
                    formatar_data(a["proxima_data"]) if a.get("proxima_data") else None,
                ],
            )
        )
        linhas.append(
            [
                chip_placa(a["placa"]),
                a["item"],
                f'<span class="mono">{_km(a["km_atual"])}</span>',
                f'<span class="mono">{proxima or "—"}</span>',
                _restante(a),
                selo_situacao(_SITUACAO_ROTULO[a["situacao"]], a["situacao"]),
            ]
        )
    tabela_html(["Moto", "Item", "Km atual", "Próxima", "Restante", "Situação"], linhas)


def _aba_historico(frota):
    todos = sorted(manutencao.listar_manutencoes(), key=lambda m: m["data_entrada"], reverse=True)
    contagem = {
        "todas": len(todos),
        "preventiva": sum(m["tipo"] == "preventiva" for m in todos),
        "corretiva": sum(m["tipo"] == "corretiva" for m in todos),
    }
    col_pills, col_busca = st.columns([3, 1.3])
    with col_pills:
        filtro = _pills("filtro_tipo", _FILTROS_TIPO, contagem)
    with col_busca:
        busca = st.text_input(
            "Buscar",
            placeholder="Buscar por moto ou oficina",
            label_visibility="collapsed",
            key="manutencao_busca_historico",
        ).casefold()

    filtrados = [
        m
        for m in todos
        if (filtro == "todas" or m["tipo"] == filtro)
        and busca in f"{frota.get(m['moto_id'], {}).get('placa', '')} {m.get('oficina') or ''}".casefold()
    ]
    pagina_atual, pagina, total_paginas = _paginar("historico", filtrados)

    st.write("")
    larguras = [1.1, 1.2, 1, 2.3, 1.4, 1.1, 1.1, 0.5]
    with st.container(key="manutencao_card_historico"):
        _cabecalho_tabela(
            st.columns(larguras, vertical_alignment="center"),
            ["Data", "Moto", "Tipo", "Descrição", "Oficina", "Custo", "Status", ""],
        )
        if not pagina_atual:
            st.markdown(
                '<div class="vazio vazio--linha">'
                "Nenhuma manutenção encontrada.</div>",
                unsafe_allow_html=True,
            )
        for registro in pagina_atual:
            moto = frota.get(registro["moto_id"])
            linha = st.columns(larguras, vertical_alignment="center")
            linha[0].markdown(_mono(formatar_data(registro["data_entrada"])), unsafe_allow_html=True)
            linha[1].markdown(chip_placa(moto["placa"]) if moto else "—", unsafe_allow_html=True)
            linha[2].markdown(_texto(registro["tipo"].capitalize()), unsafe_allow_html=True)
            linha[3].markdown(_texto(registro["descricao"]), unsafe_allow_html=True)
            linha[4].markdown(_texto(registro.get("oficina") or "—", "color:var(--texto-2);"), unsafe_allow_html=True)
            linha[5].markdown(_mono(formatar_moeda(registro["custo_total"])), unsafe_allow_html=True)
            linha[6].markdown(
                selo_situacao(_STATUS_ROTULO[registro["status"]], _STATUS_SELO[registro["status"]]),
                unsafe_allow_html=True,
            )
            if registro["status"] == "aberta" and moto:
                if linha[7].button("✓", key=f"concluir_man_{registro['id']}", help="Concluir ou cancelar"):
                    _dialog_concluir(registro, moto)
    _rodape_paginacao("historico", len(pagina_atual), len(filtrados), pagina, total_paginas)


def _interruptor(ativo):
    if ativo:
        return (
            '<div style="width:34px;height:18px;border-radius:var(--raio-md);background:var(--sucesso);position:relative;">'
            '<div style="width:14px;height:14px;border-radius:50%;background:var(--superficie);position:absolute;top:2px;right:2px;"></div></div>'
        )
    return (
        '<div style="width:34px;height:18px;border-radius:var(--raio-md);border:1px solid var(--linha);position:relative;">'
        '<div style="width:14px;height:14px;border-radius:50%;background:var(--neutro);position:absolute;top:1px;left:2px;"></div></div>'
    )


def _aba_catalogo(itens):
    _, col_botao = st.columns([5, 1])
    with col_botao:
        if st.button("+ Novo item", key="man_novo_item", use_container_width=True):
            _dialog_item({})
    st.write("")
    larguras = [3, 1.3, 1.3, 1, 0.5]
    with st.container(key="manutencao_card_catalogo"):
        _cabecalho_tabela(
            st.columns(larguras, vertical_alignment="center"),
            ["Item", "Intervalo km", "Intervalo dias", "Ativo", ""],
        )
        if not itens:
            st.markdown(
                '<div class="vazio vazio--linha">'
                "Nenhum item no catálogo.</div>",
                unsafe_allow_html=True,
            )
        for item in itens:
            muted = "" if item["ativo"] else "color:var(--texto-2);"
            linha = st.columns(larguras, vertical_alignment="center")
            linha[0].markdown(_texto(item["nome"], muted), unsafe_allow_html=True)
            linha[1].markdown(
                _mono(_km(item["intervalo_km"]), muted) if item["intervalo_km"] else _texto("—", "color:var(--texto-3);"),
                unsafe_allow_html=True,
            )
            linha[2].markdown(
                _mono(str(item["intervalo_dias"]), muted)
                if item["intervalo_dias"]
                else _texto("—", "color:var(--texto-3);"),
                unsafe_allow_html=True,
            )
            linha[3].markdown(_interruptor(item["ativo"]), unsafe_allow_html=True)
            if linha[4].button("✎", key=f"editar_item_{item['id']}", help="Editar item"):
                _dialog_item(item)


# ---------------------------------------------------------------- página --

def exibir():
    cabecalho("Manutenção", exibir_titulo=False)
    with proteger():
        frota = {m["id"]: m for m in motos.listar()}
        pendentes = [a for a in alertas.listar_manutencao() if a["situacao"] in _SITUACAO_ROTULO]
        vencidas = sum(a["situacao"] == "vencida" for a in pendentes)
        proximas = len(pendentes) - vencidas

        col_titulo, col_botao = st.columns([5, 1.4], vertical_alignment="center")
        col_titulo.markdown(
            f"""
            <h1 class="rotulo pagina-titulo">Manutenção</h1>
            <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">{vencidas} vencida(s) · {proximas} próxima(s)</div>
            """,
            unsafe_allow_html=True,
        )
        with col_botao:
            if st.button("+ Registrar manutenção", type="primary", use_container_width=True):
                _dialog_registrar()

        aba_alertas, aba_historico, aba_catalogo = st.tabs(["Alertas", "Histórico", "Catálogo"])
        with aba_alertas:
            _aba_alertas(pendentes)
        with aba_historico:
            _aba_historico(frota)
        with aba_catalogo:
            _aba_catalogo(manutencao.listar_catalogo())
