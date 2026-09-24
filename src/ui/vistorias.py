"""Vistorias: lista, registro em modal e comparação — segue Vistorias.dc.html e
VistoriaComparacao.dc.html do mockup. Também guarda o formulário compartilhado
com o assistente/encerramento de contratos (campos/preparar)."""

from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from src.domain.valores import hoje_br
from src.domain.vistorias import (
    ESTADOS_ITEM,
    NIVEIS_COMBUSTIVEL,
    checklist_inicial,
    comparar_checklists,
    contar_avarias,
    filtrar_por_tipo,
    instante_da_vistoria,
    itens_ordenados,
    km_rodados,
    resumo_avarias,
    rotulo_item,
    tipos_faltantes,
)
from src.services import clientes, contratos, motos, vistorias
from src.ui.componentes import cabecalho, chip_placa, proteger
from src.ui.formatadores import formatar_data

# ------------------------------------------------- formulário compartilhado --


def campos(chave, km):
    leitura = st.number_input(
        "Quilometragem da vistoria", min_value=km, value=km, step=1, key=chave + "_km"
    )
    combustivel = st.selectbox(
        "Combustível", ["vazio", "1/4", "1/2", "3/4", "cheio"], key=chave + "_comb"
    )
    checklist = {}
    for item in vistorias.checklist_padrao():
        checklist[item] = st.selectbox(
            item.replace("_", " ").capitalize(),
            ["ok", "avaria", "ausente", "nao_aplicavel"],
            key=chave + item,
        )
    adicionais = st.text_area(
        "Itens adicionais (um por linha: nome=estado)", key=chave + "_extras"
    )
    avarias = st.text_area("Descrição das avarias", key=chave + "_avarias")
    return {
        "km": leitura,
        "nivel_combustivel": combustivel,
        "checklist": checklist,
        "avarias": avarias,
        "adicionais": adicionais,
    }


def preparar(dados):
    dados = dict(dados)
    dados["checklist"] = dict(dados["checklist"])
    for linha in dados.pop("adicionais", "").splitlines():
        if not linha.strip():
            continue
        nome, separador, estado = linha.partition("=")
        if (
            not separador
            or not nome.strip()
            or estado.strip() not in ("ok", "avaria", "ausente", "nao_aplicavel")
        ):
            raise ValueError(
                "Use nome=estado nos itens adicionais, com estado ok, avaria, ausente ou nao_aplicavel."
            )
        dados["checklist"][nome.strip()] = estado.strip()
    return dados


# ------------------------------------------------------------------ constantes --

_FILTROS_TIPO = [("todas", "Todas"), ("entrega", "Entrega"), ("devolucao", "Devolução")]
_TIPO_ROTULO = {"entrega": "Entrega", "devolucao": "Devolução"}
# Estado do item do checklist: OK verde; avaria/ausente vermelho; N/A neutro.
_ESTADO_ITEM = {
    "ok": ("OK", "var(--sucesso-texto)"),
    "avaria": ("Avaria", "var(--perigo-texto)"),
    "ausente": ("Ausente", "var(--perigo-texto)"),
    "nao_aplicavel": ("N/A", "var(--texto-3)"),
}
_LINHA = "var(--linha)"
_POR_PAGINA = 8
_PREFIXO_REGISTRO = "vistreg_"
_FUSO = ZoneInfo("America/Sao_Paulo")


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _km(valor):
    return f"{int(valor):,} km".replace(",", ".") if valor is not None else "—"


def _combustivel(valor):
    return str(valor).capitalize() if valor else "—"


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
    """Filtros em pílula (mesmo padrão das demais listas). Devolve o valor ativo."""
    atual = st.session_state.get(f"vistorias_{chave}", padrao)
    with st.container(key=f"vistorias_filtros_{chave}"):
        colunas = st.columns(len(opcoes))
        for coluna, (valor, rotulo) in zip(colunas, opcoes):
            total = contagens.get(valor)
            texto = f"{rotulo} · {total}" if total is not None else rotulo
            if coluna.button(
                texto,
                key=f"pill_vist_{chave}_{valor}",
                type="primary" if atual == valor else "secondary",
                use_container_width=True,
            ):
                st.session_state[f"vistorias_{chave}"] = valor
                st.session_state[f"vistorias_pagina_{chave}"] = 1
                st.rerun()
    return atual


def _paginar(chave, registros):
    total_paginas = max(1, -(-len(registros) // _POR_PAGINA))
    pagina = min(st.session_state.get(f"vistorias_pagina_{chave}", 1), total_paginas)
    inicio = (pagina - 1) * _POR_PAGINA
    return registros[inicio : inicio + _POR_PAGINA], pagina, total_paginas


def _rodape_paginacao(chave, exibidos, total, pagina, total_paginas):
    if total_paginas <= 1:
        return
    st.caption(f"Mostrando {exibidos} de {total} · página {pagina} de {total_paginas}")
    anterior, proxima = st.columns(2)
    if anterior.button("‹ Anterior", disabled=pagina <= 1, key=f"vist_ant_{chave}"):
        st.session_state[f"vistorias_pagina_{chave}"] = pagina - 1
        st.rerun()
    if proxima.button("Próxima ›", disabled=pagina >= total_paginas, key=f"vist_prox_{chave}"):
        st.session_state[f"vistorias_pagina_{chave}"] = pagina + 1
        st.rerun()


# ---------------------------------------------------------------- diálogos --


def _limpar_registro():
    for chave in [c for c in st.session_state if str(c).startswith(_PREFIXO_REGISTRO)]:
        del st.session_state[chave]


def _enviar_fotos(resultado, fotos):
    """Anexa as fotos à vistoria recém-registrada. Devolve quantas falharam —
    a vistoria já está salva, então falha de foto não pode desfazê-la."""
    vistoria_id = (resultado or {}).get("vistoria_id")
    falhas = 0
    for foto in fotos or []:
        try:
            if not vistoria_id:
                raise ValueError("Vistoria sem identificador.")
            vistorias.anexar_foto(vistoria_id, foto.name, foto.getvalue(), foto.type)
        except Exception:
            falhas += 1
    return falhas


def _mensagem_fotos(base, falhas):
    if not falhas:
        return base
    return f"{base} {falhas} foto(s) não foram enviadas; anexe-as novamente pela comparação."


@st.dialog("Registrar vistoria", width="large")
def _dialog_registrar(pendentes, frota, pessoas):
    """pendentes: contratos que ainda não têm as duas vistorias."""
    if not pendentes:
        st.info("Todos os contratos já têm vistoria de entrega e de devolução.")
        return

    def rotulo(item):
        contrato, _ = item
        moto = frota.get(contrato["moto_id"], {})
        return (
            f"{pessoas.get(contrato['cliente_id'], '—')} → {moto.get('placa', '—')}"
            f" · {moto.get('marca', '')} {moto.get('modelo', '')} ({contrato['status']})"
        )

    mapa = {c["id"]: (c, faltantes) for c, faltantes in pendentes}
    escolhido = st.selectbox(
        "Contrato",
        list(mapa),
        format_func=lambda id: rotulo(mapa[id]),
        key=_PREFIXO_REGISTRO + "contrato",
    )
    contrato, faltantes = mapa[escolhido]
    moto = frota[contrato["moto_id"]]

    col_tipo, col_data, col_km = st.columns([1.4, 1, 1])
    tipo = col_tipo.radio(
        "Tipo",
        faltantes,
        format_func=_TIPO_ROTULO.get,
        horizontal=True,
        key=f"{_PREFIXO_REGISTRO}tipo_{escolhido}",
    )
    dia = col_data.date_input(
        "Data",
        hoje_br(),
        max_value=hoje_br(),
        format="DD/MM/YYYY",
        key=_PREFIXO_REGISTRO + "data",
    )
    km = col_km.number_input(
        "Km",
        min_value=moto["km_atual"],
        value=moto["km_atual"],
        step=1,
        key=f"{_PREFIXO_REGISTRO}km_{escolhido}",
    )
    combustivel = st.radio(
        "Nível de combustível",
        NIVEIS_COMBUSTIVEL,
        index=len(NIVEIS_COMBUSTIVEL) - 1,
        format_func=_combustivel,
        horizontal=True,
        key=_PREFIXO_REGISTRO + "combustivel",
    )

    st.caption("Checklist")
    checklist = {}
    esquerda, direita = st.columns(2)
    for indice, item in enumerate(checklist_inicial()):
        coluna = esquerda if indice % 2 == 0 else direita
        checklist[item] = coluna.selectbox(
            rotulo_item(item),
            ESTADOS_ITEM,
            format_func=lambda e: _ESTADO_ITEM[e][0],
            key=f"{_PREFIXO_REGISTRO}item_{item}",
        )
    with st.expander("Itens adicionais"):
        adicionais = st.text_area(
            "Um por linha, no formato nome=estado (ok, avaria, ausente ou nao_aplicavel)",
            height=80,
            key=_PREFIXO_REGISTRO + "adicionais",
        )
    avarias = st.text_area(
        "Avarias (se houver)",
        height=80,
        placeholder="Descreva arranhões, amassados ou peças com defeito",
        key=_PREFIXO_REGISTRO + "avarias",
    )
    fotos = st.file_uploader(
        "Fotos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=_PREFIXO_REGISTRO + "fotos",
    )

    col_cancelar, col_salvar = st.columns(2)
    if col_cancelar.button("Cancelar", use_container_width=True, key=_PREFIXO_REGISTRO + "cancelar"):
        _limpar_registro()
        st.rerun()
    if col_salvar.button(
        "Salvar vistoria", type="primary", use_container_width=True, key=_PREFIXO_REGISTRO + "salvar"
    ):
        with proteger():
            if dia < date.fromisoformat(str(contrato["data_inicio"])[:10]):
                raise ValueError("A data da vistoria não pode anteceder o início do contrato.")
            dados = preparar(
                {
                    "km": km,
                    "nivel_combustivel": combustivel,
                    "checklist": checklist,
                    "avarias": avarias.strip() or None,
                    "adicionais": adicionais,
                }
            )
            resultado = vistorias.registrar_vistoria(
                contrato["id"],
                contrato["moto_id"],
                tipo,
                data=instante_da_vistoria(dia, datetime.now(_FUSO)),
                **dados,
            )
            falhas = _enviar_fotos(resultado, fotos)
            _limpar_registro()
            _salvo(_mensagem_fotos("Vistoria registrada.", falhas))


@st.dialog("Adicionar fotos")
def _dialog_fotos(vistoria):
    st.write(f"Vistoria de {_TIPO_ROTULO[vistoria['tipo']].lower()} · {formatar_data(vistoria['data'])}")
    fotos = st.file_uploader(
        "Fotos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="vistfotos_" + vistoria["id"],
    )
    if st.button(
        "Salvar fotos",
        type="primary",
        use_container_width=True,
        disabled=not fotos,
        key="vistfotos_salvar_" + vistoria["id"],
    ):
        with proteger():
            falhas = _enviar_fotos({"vistoria_id": vistoria["id"]}, fotos)
            if falhas == len(fotos):
                raise ValueError("Não foi possível enviar as fotos. Confira os arquivos e tente novamente.")
            _salvo(_mensagem_fotos("Fotos anexadas.", falhas))


# ------------------------------------------------------------------- lista --


def _rotulo_contrato(contrato, frota, pessoas):
    if not contrato:
        return "—"
    moto = frota.get(contrato["moto_id"])
    nome = escape(pessoas.get(contrato["cliente_id"], "—"))
    placa = chip_placa(moto["placa"]) if moto else "—"
    return f'{_texto(nome)} <span style="color:var(--texto-2);">→</span> {placa}'


def _abrir_comparacao(contrato_id):
    st.session_state["vistorias_visao"] = "comparacao"
    st.session_state["vistorias_contrato"] = contrato_id
    st.rerun()


def _voltar_lista():
    st.session_state["vistorias_visao"] = "lista"
    st.session_state.pop("vistorias_contrato", None)
    st.rerun()


def _exibir_lista(todas, contratos_por_id, frota, pessoas):
    tipos_por_contrato = {}
    for v in todas:
        tipos_por_contrato.setdefault(v["contrato_id"], []).append(v)
    pendentes = [
        (c, faltantes)
        for c in contratos_por_id.values()
        if c["moto_id"] in frota
        and (faltantes := tipos_faltantes(tipos_por_contrato.get(c["id"], [])))
    ]

    col_titulo, col_botao = st.columns([5, 1.6], vertical_alignment="center")
    col_titulo.markdown(
        """
        <h1 class="rotulo pagina-titulo">Vistorias</h1>
        <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">Entregas e devoluções registradas</div>
        """,
        unsafe_allow_html=True,
    )
    with col_botao:
        if st.button("+ Registrar vistoria", type="primary", use_container_width=True):
            _dialog_registrar(pendentes, frota, pessoas)

    contagem = {valor: len(filtrar_por_tipo(todas, valor)) for valor, _ in _FILTROS_TIPO}
    col_pills, col_busca = st.columns([3, 1.3])
    with col_pills:
        filtro = _pills("filtro_tipo", _FILTROS_TIPO, contagem)
    with col_busca:
        busca = st.text_input(
            "Buscar",
            placeholder="Buscar por cliente ou placa",
            label_visibility="collapsed",
            key="vistorias_busca",
        ).casefold()

    def texto_busca(v):
        contrato = contratos_por_id.get(v["contrato_id"], {})
        moto = frota.get(contrato.get("moto_id"), {})
        return f"{pessoas.get(contrato.get('cliente_id'), '')} {moto.get('placa', '')}".casefold()

    filtradas = [
        v
        for v in filtrar_por_tipo(todas, filtro)
        if busca.replace("-", "") in texto_busca(v)
    ]
    filtradas.sort(key=lambda v: v["data"], reverse=True)
    pagina_atual, pagina, total_paginas = _paginar("lista", filtradas)

    st.write("")
    larguras = [1.1, 2.6, 1, 1.1, 1.1, 2.4, 0.5]
    with st.container(key="vistorias_card_lista"):
        _cabecalho_tabela(
            st.columns(larguras, vertical_alignment="center"),
            ["Data", "Contrato", "Tipo", "Km", "Combustível", "Avarias", ""],
        )
        if not pagina_atual:
            st.markdown(
                '<div class="vazio vazio--linha">'
                "Nenhuma vistoria encontrada.</div>",
                unsafe_allow_html=True,
            )
        for v in pagina_atual:
            contrato = contratos_por_id.get(v["contrato_id"])
            avarias = resumo_avarias(v)
            linha = st.columns(larguras, vertical_alignment="center")
            linha[0].markdown(_mono(formatar_data(v["data"])), unsafe_allow_html=True)
            linha[1].markdown(_rotulo_contrato(contrato, frota, pessoas), unsafe_allow_html=True)
            linha[2].markdown(_texto(_TIPO_ROTULO[v["tipo"]]), unsafe_allow_html=True)
            linha[3].markdown(_mono(_km(v["km"])), unsafe_allow_html=True)
            linha[4].markdown(_texto(_combustivel(v.get("nivel_combustivel"))), unsafe_allow_html=True)
            linha[5].markdown(
                _texto(escape(avarias), "color:var(--perigo-texto);") if avarias else _texto("Nenhuma", "color:var(--texto-2);"),
                unsafe_allow_html=True,
            )
            if contrato and linha[6].button("›", key=f"ver_vist_{v['id']}", help="Ver comparação"):
                _abrir_comparacao(contrato["id"])
    _rodape_paginacao("lista", len(pagina_atual), len(filtradas), pagina, total_paginas)


# -------------------------------------------------------------- comparação --


def _campo(rotulo, valor_html):
    return (
        f'<div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">{rotulo}</span>'
        f'<span style="font-size:var(--fs-secundario);">{valor_html}</span></div>'
    )


def _miniatura(url, legenda):
    estilo = "width:90px;height:66px;border-radius:var(--raio-sm);"
    if not url:
        return f'<div style="{estilo}background:{_LINHA};"></div>'
    return (
        f'<img src="{escape(url, quote=True)}" alt="{escape(legenda or "Foto da vistoria", quote=True)}" '
        f'style="{estilo}object-fit:cover;">'
    )


def _url_foto(foto):
    try:
        return vistorias.url_foto(foto["storage_path"])
    except Exception:
        return None


def _html_cartao(titulo, vistoria, diferentes):
    itens = itens_ordenados(vistoria.get("checklist"))
    avarias = resumo_avarias(vistoria)
    linhas = ""
    for indice, (chave, estado) in enumerate(itens):
        rotulo, cor = _ESTADO_ITEM.get(estado, (str(estado), "var(--texto-3)"))
        fundo = "background:var(--alerta-fundo);" if chave in diferentes else ""
        borda = "" if indice == len(itens) - 1 else f"border-bottom:1px solid {_LINHA};"
        linhas += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:7px 10px;{borda}{fundo}font-size:var(--fs-legenda);">'
            f'<span>{escape(rotulo_item(chave))}</span>'
            f'<span style="color:{cor};font-weight:600;">{escape(rotulo)}</span></div>'
        )
    checklist = (
        f'<div style="font-size:var(--fs-legenda);color:var(--texto-2);margin-bottom:6px;">checklist</div>{linhas}'
        if linhas
        else '<div style="font-size:var(--fs-legenda);color:var(--texto-2);">Checklist não preenchido.</div>'
    )
    fotos = "".join(_miniatura(_url_foto(f), f.get("legenda")) for f in vistoria.get("fotos", []))
    fotos = fotos or '<span style="font-size:var(--fs-legenda);color:var(--texto-2);">Nenhuma foto anexada.</span>'
    return f"""
    <div style="background:var(--superficie);border:1px solid {_LINHA};border-radius:var(--raio-lg);padding:20px 22px;">
      <h3 class="rotulo" style="margin:0 0 14px;font-size:15px;">{titulo}</h3>
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:16px;">
        {_campo("data", _mono(formatar_data(vistoria["data"])))}
        {_campo("km", _mono(_km(vistoria["km"])))}
        {_campo("combustível", escape(_combustivel(vistoria.get("nivel_combustivel"))))}
        {_campo("avarias", f'<span style="color:var(--perigo-texto);">{escape(avarias)}</span>' if avarias else "Nenhuma")}
      </div>
      <div style="margin-bottom:16px;">{checklist}</div>
      <div style="font-size:var(--fs-legenda);color:var(--texto-2);margin-bottom:6px;">fotos</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">{fotos}</div>
    </div>
    """


def _html_cartao_vazio(titulo, tipo):
    complemento = (
        " — será registrada no encerramento do contrato." if tipo == "devolucao" else "."
    )
    return f"""
    <div style="background:var(--superficie);border:1px dashed {_LINHA};border-radius:var(--raio-sm);padding:20px 22px;">
      <h3 class="rotulo" style="margin:0 0 8px;font-size:15px;color:var(--texto-2);">{titulo}</h3>
      <div class="fs-secundario texto-2">Ainda não realizada{complemento}</div>
    </div>
    """


def _faixa_resumo(contrato, entrega, devolucao):
    periodo = f"{formatar_data(contrato['data_inicio'])} – " + (
        formatar_data(contrato["data_encerramento"]) if contrato.get("data_encerramento") else "em andamento"
    )
    rodados = km_rodados(entrega, devolucao)
    if devolucao is None:
        avarias = '<span style="color:var(--texto-2);">—</span>'
    else:
        total = contar_avarias(devolucao)
        avarias = f'<span style="color:var(--perigo-texto);">{total} registrada(s)</span>' if total else "Nenhuma"
    celulas = [
        ("contrato", _mono(periodo)),
        ("km rodados", _mono(_km(rodados))),
        ("avarias na devolução", avarias),
    ]
    blocos = "".join(
        f'<div class="campo" style="flex:1;padding:14px 22px;justify-content:center;'
        f'{"border-right:1px solid " + _LINHA + ";" if i < len(celulas) - 1 else ""}">'
        f'<span style="font-size:var(--fs-legenda);color:var(--texto-2);">{rotulo}</span>'
        f'<span style="font-size:var(--fs-secundario);">{valor}</span></div>'
        for i, (rotulo, valor) in enumerate(celulas)
    )
    st.markdown(
        f'<div style="display:flex;background:var(--superficie);border:1px solid {_LINHA};'
        f'border-radius:var(--raio-sm);margin-bottom:20px;">{blocos}</div>',
        unsafe_allow_html=True,
    )


def _exibir_comparacao(contratos_por_id, frota, pessoas):
    contrato = contratos_por_id.get(st.session_state.get("vistorias_contrato"))
    moto = frota.get(contrato["moto_id"]) if contrato else None
    if not contrato or not moto:
        st.warning("Contrato não encontrado.")
        _voltar_lista()
        return

    if st.button("‹ Vistorias", key="voltar_vistorias"):
        _voltar_lista()

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;margin:6px 0 20px;">'
        f'<h1 class="rotulo" style="margin:0;font-size:22px;color:var(--texto);">'
        f'{escape(pessoas.get(contrato["cliente_id"], "—"))} → {escape(moto["marca"])} {escape(moto["modelo"])}</h1>'
        f'{chip_placa(moto["placa"], "grande")}</div>',
        unsafe_allow_html=True,
    )

    comparacao = vistorias.comparar_entrega_devolucao(contrato["id"])
    entrega, devolucao = comparacao["entrega"], comparacao["devolucao"]
    _faixa_resumo(contrato, entrega, devolucao)

    diferentes = set(
        comparar_checklists(
            (entrega or {}).get("checklist"), (devolucao or {}).get("checklist")
        )
        if entrega and devolucao
        else ()
    )
    col_entrega, col_devolucao = st.columns(2, gap="medium")
    for coluna, tipo, vistoria in [
        (col_entrega, "entrega", entrega),
        (col_devolucao, "devolucao", devolucao),
    ]:
        titulo = _TIPO_ROTULO[tipo]
        with coluna:
            if not vistoria:
                st.markdown(_html_cartao_vazio(titulo, tipo), unsafe_allow_html=True)
                continue
            st.markdown(_html_cartao(titulo, vistoria, diferentes), unsafe_allow_html=True)
            if st.button("Adicionar fotos", key=f"add_fotos_{vistoria['id']}"):
                _dialog_fotos(vistoria)
    if diferentes:
        st.caption("Itens com fundo amarelo mudaram entre a entrega e a devolução.")


# ---------------------------------------------------------------- página --


def exibir():
    cabecalho("Vistorias", exibir_titulo=False)
    with proteger():
        frota = {m["id"]: m for m in motos.listar()}
        pessoas = {c["id"]: c["nome"] for c in clientes.listar()}
        contratos_por_id = {c["id"]: c for c in contratos.listar()}
        if st.session_state.get("vistorias_visao") == "comparacao":
            _exibir_comparacao(contratos_por_id, frota, pessoas)
        else:
            _exibir_lista(vistorias.listar(), contratos_por_id, frota, pessoas)
