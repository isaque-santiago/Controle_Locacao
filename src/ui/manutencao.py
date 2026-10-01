"""Manutenção: alertas, histórico e catálogo — segue Manutencao.dc.html do mockup."""

from decimal import Decimal
from html import escape

import streamlit as st

from src.services import manutencao, motos, alertas
from src.domain.valores import hoje_br, decimal_br
from src.domain.manutencao_regras import preparar_itens_adicionais
from src.ui.componentes import (
    cabecalho,
    cabecalho_pagina,
    vazio_lista,
    proteger,
    selecionar,
    chip_placa,
    selo_situacao,
    tabela_html,
    botao_acao,
)
from src.ui.listas import abas, aba_ativa, barra_filtros, paginar, rodape_paginacao
from src.ui.formatadores import formatar_data, formatar_moeda, formatar_placa
from src.ui.registros import campo, lista_registros, registro

_SITUACAO_ROTULO = {"vencida": "Vencida", "proxima": "Próxima"}
_FILTROS_ALERTA = [("todas", "Todas"), ("vencida", "Vencidas"), ("proxima", "Próximas")]
_FILTROS_TIPO = [("todas", "Todas"), ("preventiva", "Preventiva"), ("corretiva", "Corretiva")]
_STATUS_ROTULO = {"aberta": "Aberta", "concluida": "Concluída", "cancelada": "Cancelada"}
# "aberta" é estado operacional (sem tinta); concluída usa o verde de "ok".
_STATUS_SELO = {"aberta": "aberta", "concluida": "ok", "cancelada": "cancelada"}
_PREFIXO_REGISTRO = "manreg_"
_CHAVE_EXTRAS = _PREFIXO_REGISTRO + "extras_ids"


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


def _adicionar_linha():
    ids = st.session_state.setdefault(_CHAVE_EXTRAS, [])
    ids.append(max(ids, default=-1) + 1)


def _remover_linha(n):
    st.session_state[_CHAVE_EXTRAS].remove(n)


def _linhas_adicionais():
    """Peças e serviços fora do plano: uma linha de campos por item (com rótulos visíveis e botão
    `Remover`), no lugar da tabela editável em canvas, que não segue o tema nem funciona bem no celular.
    Adicionar e remover são callbacks (rodam antes da reexecução, também dentro do diálogo).
    Devolve os registros no formato de `preparar_itens_adicionais`."""
    ids = st.session_state.setdefault(_CHAVE_EXTRAS, [])
    st.caption("Outras peças ou serviços")
    registros = []
    for n in ids:
        c_desc, c_qtd, c_valor, c_remover = st.columns([3, 1, 1.4, 1.2], vertical_alignment="bottom")
        descricao = c_desc.text_input("Descrição", key=f"{_PREFIXO_REGISTRO}extra_desc_{n}")
        quantidade = c_qtd.text_input("Quantidade", "1", key=f"{_PREFIXO_REGISTRO}extra_qtd_{n}")
        valor = c_valor.text_input("Valor unitário (R$)", "0", key=f"{_PREFIXO_REGISTRO}extra_valor_{n}")
        botao_acao(
            c_remover,
            "remover",
            f"{_PREFIXO_REGISTRO}extra_remover_{n}",
            ajuda=f"Remover {descricao.strip() or 'esta linha'} da lista de peças e serviços",
            on_click=_remover_linha,
            args=(n,),
        )
        registros.append({"descricao": descricao, "quantidade": quantidade, "valor_unitario": valor})
    st.button(
        "Adicionar peça ou serviço",
        key=_PREFIXO_REGISTRO + "extra_adicionar",
        icon=":material/add:",
        on_click=_adicionar_linha,
    )
    return registros


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

    registros_adicionais = _linhas_adicionais()

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


_IMPACTO_FINALIZAR = {
    "concluida": (
        "Ao concluir, a quilometragem é registrada, o plano de manutenção dos itens feitos "
        "é reiniciado e a moto sai de manutenção quando não houver outro serviço aberto."
    ),
    "cancelada": (
        "Ao cancelar, o serviço deixa de ser contado: o plano de manutenção não é reiniciado "
        "e nada é cobrado do cliente. A moto sai de manutenção quando não houver outro serviço aberto. "
        "Não é possível reabrir a manutenção depois."
    ),
}


def _finalizar_manutencao(registro, moto, acao):
    """Corpo compartilhado dos diálogos Concluir e Cancelar manutenção: cada um faz uma só coisa."""
    concluir = acao == "concluida"
    st.markdown(chip_placa(moto["placa"]), unsafe_allow_html=True)
    st.write(f"{formatar_data(registro['data_entrada'])} · {registro['descricao']}")
    (st.caption if concluir else st.warning)(_IMPACTO_FINALIZAR[acao])
    piso = max(moto["km_atual"], registro["km"])
    with st.form(("form_concluir_" if concluir else "form_cancelar_") + registro["id"]):
        data_saida = st.date_input(
            "Data de conclusão" if concluir else "Data do cancelamento", hoje_br(), format="DD/MM/YYYY"
        )
        km = st.number_input("Km na conclusão" if concluir else "Km atual da moto", min_value=piso, value=piso, step=1)
        if st.form_submit_button(
            "Concluir manutenção" if concluir else "Cancelar manutenção",
            type="primary",
            use_container_width=True,
            key=None if concluir else "perigo_confirmar_cancelar_man",
        ):
            with proteger():
                manutencao.finalizar(registro["id"], acao, data_saida, km)
                _salvo("Manutenção concluída." if concluir else "Manutenção cancelada.")


@st.dialog("Concluir manutenção")
def _dialog_concluir(registro, moto):
    _finalizar_manutencao(registro, moto, "concluida")


@st.dialog("Cancelar manutenção")
def _dialog_cancelar(registro, moto):
    _finalizar_manutencao(registro, moto, "cancelada")


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
    filtros = barra_filtros("manutencao_alertas", _FILTROS_ALERTA, padrao="todas", contagens=contagem)
    visiveis = [a for a in pendentes if filtros.valor == "todas" or a["situacao"] == filtros.valor]
    filtros.resumo(len(visiveis), ("alerta", "alertas"))
    visiveis.sort(
        key=lambda a: (
            a["situacao"] != "vencida",
            a["km_restantes"] if a.get("km_restantes") is not None else float("inf"),
        )
    )
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
    tabela_html(
        ["Moto", "Item", "Km atual", "Próxima", "Restante", "Situação"],
        linhas,
        legenda="Alertas de manutenção",
        vazio=vazio_lista(
            "Nenhum alerta neste filtro.",
            "Nenhuma manutenção vencida ou próxima.",
            bool(pendentes),
        ),
    )


def _aba_historico(frota):
    todos = sorted(manutencao.listar_manutencoes(), key=lambda m: m["data_entrada"], reverse=True)
    contagem = {
        "todas": len(todos),
        "preventiva": sum(m["tipo"] == "preventiva" for m in todos),
        "corretiva": sum(m["tipo"] == "corretiva" for m in todos),
    }
    filtros = barra_filtros(
        "manutencao_historico",
        _FILTROS_TIPO,
        padrao="todas",
        contagens=contagem,
        grupo="Tipo",
        busca="Buscar por moto ou oficina",
    )
    busca = filtros.busca.casefold()

    filtrados = [
        m
        for m in todos
        if (filtros.valor == "todas" or m["tipo"] == filtros.valor)
        and busca in f"{frota.get(m['moto_id'], {}).get('placa', '')} {m.get('oficina') or ''}".casefold()
    ]
    filtros.resumo(len(filtrados), ("manutenção", "manutenções"))
    pagina_atual, pagina = paginar("manutencao_historico", filtrados)

    st.write("")
    with lista_registros("manutencao_historico", acoes=2):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhuma manutenção encontrada.", "Ainda não há manutenções registradas.", bool(todos), "Registrar manutenção"),
                unsafe_allow_html=True,
            )
        for registro_man in pagina_atual:
            moto = frota.get(registro_man["moto_id"])
            aberta = registro_man["status"] == "aberta" and moto
            campos = [
                campo("Data", _mono(formatar_data(registro_man["data_entrada"]))),
                campo("Tipo", _texto(registro_man["tipo"].capitalize())),
                campo("Oficina", _texto(escape(registro_man.get("oficina") or "—"), "color:var(--texto-2);")),
                campo("Custo", _mono(formatar_moeda(registro_man["custo_total"]))),
                campo("Descrição", _texto(escape(registro_man["descricao"])), largo=True),
            ]
            with registro(
                "manutencao_historico",
                registro_man["id"],
                chip_placa(moto["placa"]) if moto else "—",
                campos,
                selo=selo_situacao(_STATUS_ROTULO[registro_man["status"]], _STATUS_SELO[registro_man["status"]]),
                acoes=bool(aberta),
            ) as acoes:
                if aberta:
                    # Duas ações distintas: concluir e cancelar nunca dividem o mesmo botão
                    if botao_acao(
                        acoes,
                        "concluir",
                        f"concluir_man_{registro_man['id']}",
                        ajuda=f"Concluir a manutenção da moto {formatar_placa(moto['placa'])}",
                    ):
                        _dialog_concluir(registro_man, moto)
                    if botao_acao(
                        acoes,
                        "cancelar",
                        f"cancelar_man_{registro_man['id']}",
                        ajuda=f"Cancelar a manutenção da moto {formatar_placa(moto['placa'])}",
                    ):
                        _dialog_cancelar(registro_man, moto)
    rodape_paginacao("manutencao_historico", pagina)


def _aba_catalogo(itens):
    _, col_botao = st.columns([5, 1])
    with col_botao:
        if st.button("+ Novo item", key="man_novo_item", use_container_width=True):
            _dialog_item({})
    st.write("")
    with lista_registros("manutencao_catalogo", acoes=1):
        if not itens:
            st.markdown(
                vazio_lista("Nenhum item no catálogo.", "Ainda não há itens no catálogo.", False),
                unsafe_allow_html=True,
            )
        for item in itens:
            muted = "" if item["ativo"] else "color:var(--texto-2);"
            campos = [
                campo(
                    "Intervalo km",
                    _mono(_km(item["intervalo_km"]), muted) if item["intervalo_km"] else _texto("—", "color:var(--texto-3);"),
                ),
                campo(
                    "Intervalo dias",
                    _mono(str(item["intervalo_dias"]), muted) if item["intervalo_dias"] else _texto("—", "color:var(--texto-3);"),
                ),
            ]
            with registro(
                "manutencao_catalogo",
                item["id"],
                _texto(escape(item["nome"]), muted),
                campos,
                selo=selo_situacao("Ativo" if item["ativo"] else "Inativo", "ativo" if item["ativo"] else "inativo"),
            ) as acoes:
                if botao_acao(acoes, "editar", f"editar_item_{item['id']}", ajuda=f"Editar o item {item['nome']}"):
                    _dialog_item(item)


# ---------------------------------------------------------------- página --

def exibir():
    cabecalho("Manutenção", exibir_titulo=False)
    with proteger():
        frota = {m["id"]: m for m in motos.listar()}
        pendentes = [a for a in alertas.listar_manutencao() if a["situacao"] in _SITUACAO_ROTULO]
        vencidas = sum(a["situacao"] == "vencida" for a in pendentes)
        proximas = len(pendentes) - vencidas

        if cabecalho_pagina(
            "Manutenção",
            sub=f"{vencidas} vencida(s) · {proximas} próxima(s)",
            acao={"rotulo": "Registrar manutenção", "chave": "manutencao_registrar"},
        ):
            _dialog_registrar()

        guias = abas("manutencao_abas", ["Alertas", "Histórico", "Catálogo"])
        desenho = (
            lambda: _aba_alertas(pendentes),
            lambda: _aba_historico(frota),
            lambda: _aba_catalogo(manutencao.listar_catalogo()),
        )
        for guia, desenhar in zip(guias, desenho):
            with guia:
                if aba_ativa(guia):
                    desenhar()
