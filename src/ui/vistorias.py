"""Vistorias: lista, registro em modal e comparação — segue Vistorias.dc.html e
VistoriaComparacao.dc.html do mockup. Também guarda o formulário compartilhado
com o assistente/encerramento de contratos (campos/preparar)."""

from contextlib import nullcontext
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from src.domain import mensagens
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
from src.ui.componentes import (
    botao_acao,
    botao_voltar,
    cabecalho,
    cabecalho_ficha,
    cabecalho_pagina,
    cartao_dados,
    chip_placa,
    dado,
    faixa_dados,
    ficha_identidade,
    grade_dados,
    paineis,
    proteger,
    vazio_lista,
)
from src.ui import feedback
from src.domain.formatadores import formatar_data, formatar_placa
from src.ui.formularios import campo_inteiro, linha_campos, rodape_formulario
from src.ui.listas import barra_filtros, lembrar_registro, paginar, restaurar_posicao, rodape_paginacao
from src.ui.registros import campo, lista_registros, registro

# ------------------------------------------------- formulário compartilhado --


def campos(chave, km, ajuda_km=None):
    """Campos da vistoria dentro de outro formulário (entrega no assistente, devolução no
    encerramento). Os itens do checklist ficam em pares, na ordem de leitura, e empilham em tela estreita."""
    leitura = campo_inteiro(
        "Quilometragem da vistoria", km, chave + "_km", sufixo="km", minimo=km, ajuda=ajuda_km
    )
    combustivel = st.selectbox(
        "Combustível", list(NIVEIS_COMBUSTIVEL), format_func=_combustivel, key=chave + "_comb"
    )
    st.caption("Checklist")
    checklist = {}
    itens = list(vistorias.checklist_padrao())
    for inicio in range(0, len(itens), 2):
        with linha_campos([1, 1], f"{chave}_item_{inicio}") as colunas:
            for coluna, item in zip(colunas, itens[inicio : inicio + 2]):
                checklist[item] = coluna.selectbox(
                    rotulo_item(item),
                    list(ESTADOS_ITEM),
                    format_func=lambda estado: _ESTADO_ITEM[estado][0],
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
# Estado do item do checklist: rótulo e tom (OK verde; avaria/ausente vermelho; N/A neutro). O estado
# é sempre escrito, nunca só colorido.
_ESTADO_ITEM = {
    "ok": ("OK", "ok"),
    "avaria": ("Avaria", "ruim"),
    "ausente": ("Ausente", "ruim"),
    "nao_aplicavel": ("N/A", "na"),
}
_PREFIXO_REGISTRO = "vistreg_"
_FUSO = ZoneInfo("America/Sao_Paulo")


def _km(valor):
    return f"{int(valor):,} km".replace(",", ".") if valor is not None else "—"


def _combustivel(valor):
    return str(valor).capitalize() if valor else "—"


def _mono(texto, classe=""):
    return f'<span class="mono fs-secundario {classe}">{texto}</span>'


def _texto(texto, classe=""):
    return f'<span class="fs-secundario {classe}">{texto}</span>'


# ---------------------------------------------------------------- diálogos --


def _limpar_registro():
    for chave in [c for c in st.session_state if str(c).startswith(_PREFIXO_REGISTRO)]:
        del st.session_state[chave]


def _enviar_fotos(resultado, fotos):
    """Anexa as fotos à vistoria recém-registrada. Devolve quantas falharam —
    a vistoria já está salva, então falha de foto não pode desfazê-la."""
    vistoria_id = (resultado or {}).get("vistoria_id")
    falhas = 0
    with st.spinner("Enviando as fotos…") if fotos else nullcontext():
        for foto in fotos or []:
            try:
                if not vistoria_id:
                    raise ValueError("Vistoria sem identificador.")
                vistorias.anexar_foto(vistoria_id, foto.name, foto.getvalue(), foto.type)
            except Exception:
                falhas += 1
    return falhas


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

    tipo = st.radio(
        "Tipo",
        faltantes,
        format_func=_TIPO_ROTULO.get,
        horizontal=True,
        key=f"{_PREFIXO_REGISTRO}tipo_{escolhido}",
    )
    inicio_contrato = date.fromisoformat(str(contrato["data_inicio"])[:10])
    with linha_campos([1, 1], "vist_data_km") as (col_data, col_km):
        dia = col_data.date_input(
            "Data",
            hoje_br(),
            max_value=hoje_br(),
            format="DD/MM/YYYY",
            key=_PREFIXO_REGISTRO + "data",
        )
        with col_km:
            km = campo_inteiro(
                "Km",
                moto["km_atual"],
                f"{_PREFIXO_REGISTRO}km_{escolhido}",
                sufixo="km",
                minimo=moto["km_atual"],
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
    itens = list(checklist_inicial())
    for inicio in range(0, len(itens), 2):
        with linha_campos([1, 1], f"vist_check_{inicio}") as colunas:
            for coluna, item in zip(colunas, itens[inicio : inicio + 2]):
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

    erro = None
    if not dia:
        erro = "Data: informe a data da vistoria."
    elif dia < inicio_contrato:
        erro = f"Data: a vistoria não pode anteceder o início do contrato ({formatar_data(inicio_contrato.isoformat())})."
    acao = rodape_formulario("Salvar vistoria", "vistreg", desabilitado=bool(erro), motivo=erro)
    if acao.cancelou:
        _limpar_registro()
        st.rerun()
    if acao.confirmou:
        with proteger():
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
            feedback.concluir(
                mensagens.vistoria_registrada(_TIPO_ROTULO[tipo].lower(), formatar_placa(moto["placa"]), falhas)
            )


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
        key="ocupa_vistfotos_salvar_" + vistoria["id"],
    ):
        with proteger():
            falhas = _enviar_fotos({"vistoria_id": vistoria["id"]}, fotos)
            if falhas == len(fotos):
                raise ValueError("Não foi possível enviar as fotos. Confira os arquivos e tente novamente.")
            feedback.concluir(mensagens.fotos_anexadas(len(fotos) - falhas, falhas))


# ------------------------------------------------------------------- lista --


def _abrir_comparacao(contrato_id, vistoria_id):
    lembrar_registro("vistorias", vistoria_id)
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

    if cabecalho_pagina(
        "Vistorias",
        sub="Entregas e devoluções registradas",
        acao={"rotulo": "Registrar vistoria", "chave": "vistorias_registrar"},
    ):
        _dialog_registrar(pendentes, frota, pessoas)

    contagem = {valor: len(filtrar_por_tipo(todas, valor)) for valor, _ in _FILTROS_TIPO}
    filtros = barra_filtros(
        "vistorias",
        _FILTROS_TIPO,
        padrao="todas",
        contagens=contagem,
        grupo="Tipo",
        busca="Buscar por cliente ou placa",
    )
    busca = filtros.busca.casefold()

    def texto_busca(v):
        contrato = contratos_por_id.get(v["contrato_id"], {})
        moto = frota.get(contrato.get("moto_id"), {})
        return f"{pessoas.get(contrato.get('cliente_id'), '')} {moto.get('placa', '')}".casefold()

    filtradas = [
        v
        for v in filtrar_por_tipo(todas, filtros.valor)
        if busca.replace("-", "") in texto_busca(v)
    ]
    filtradas.sort(key=lambda v: v["data"], reverse=True)
    filtros.resumo(len(filtradas), ("vistoria", "vistorias"))
    pagina_atual, pagina = paginar("vistorias", filtradas)

    with lista_registros("vistorias", acoes=1):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhuma vistoria encontrada.", "Ainda não há vistorias registradas.", bool(todas), "Registrar vistoria"),
                unsafe_allow_html=True,
            )
        for v in pagina_atual:
            contrato = contratos_por_id.get(v["contrato_id"])
            moto = frota.get(contrato["moto_id"]) if contrato else None
            cliente = pessoas.get(contrato["cliente_id"], "—") if contrato else "—"
            avarias = resumo_avarias(v)
            campos = [
                campo("Moto", chip_placa(moto["placa"]) if moto else "—"),
                campo("Data", _mono(formatar_data(v["data"]))),
                campo("Tipo", _texto(_TIPO_ROTULO[v["tipo"]])),
                campo("Km", _mono(_km(v["km"]))),
                campo("Combustível", _texto(_combustivel(v.get("nivel_combustivel")))),
                campo(
                    "Avarias",
                    _texto(escape(avarias), "texto-perigo") if avarias else _texto("Nenhuma", "texto-2"),
                    largo=True,
                ),
            ]
            with registro("vistorias", v["id"], _texto(escape(cliente)), campos, acoes=bool(contrato)) as acoes:
                if contrato and botao_acao(
                    acoes,
                    "comparar",
                    f"ver_vist_{v['id']}",
                    ajuda=f"Comparar as vistorias do contrato (vistoria de {formatar_data(v['data'])})",
                ):
                    _abrir_comparacao(contrato["id"], v["id"])
    rodape_paginacao("vistorias", pagina)
    restaurar_posicao("vistorias")


# -------------------------------------------------------------- comparação --


def _foto(url, legenda):
    """Miniatura da galeria: a foto inteira (retrato ou paisagem) numa moldura 4:3; o clique abre a original."""
    if not url:
        return '<li><div class="galeria__foto galeria__vazia">Foto indisponível</div></li>'
    texto = escape(legenda or "Foto da vistoria", quote=True)
    return (
        f'<li><a class="galeria__foto" href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer" '
        f'aria-label="{texto} (abre em nova aba)"><img src="{escape(url, quote=True)}" alt="{texto}" loading="lazy" decoding="async"></a></li>'
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
    for chave, estado in itens:
        rotulo, tom = _ESTADO_ITEM.get(estado, (str(estado), "na"))
        mudou = chave in diferentes
        aviso = '<span class="vist-item__mudou">alterado</span>' if mudou else ""
        linhas += (
            f'<li class="vist-item{" vist-item--mudou" if mudou else ""}">'
            f'<span class="vist-item__nome">{escape(rotulo_item(chave))}</span>'
            f'<span><span class="vist-item__estado vist-item__estado--{tom}">{escape(rotulo)}</span>{aviso}</span></li>'
        )
    checklist = (
        f'<div><div class="vist-secao">Checklist</div><ul class="vist-checklist">{linhas}</ul></div>'
        if linhas
        else '<div class="fs-legenda texto-2">Checklist não preenchido.</div>'
    )
    fotos = "".join(_foto(_url_foto(f), f.get("legenda")) for f in vistoria.get("fotos", []))
    galeria = (
        f'<ul class="galeria">{fotos}</ul>' if fotos else '<div class="fs-legenda texto-2">Nenhuma foto anexada.</div>'
    )
    corpo = (
        '<div class="vist-cartao">'
        + grade_dados(
            [
                dado("Data", f'<span class="mono">{formatar_data(vistoria["data"])}</span>'),
                dado("Km", f'<span class="mono">{_km(vistoria["km"])}</span>'),
                dado("Combustível", escape(_combustivel(vistoria.get("nivel_combustivel")))),
                dado(
                    "Avarias",
                    f'<span class="texto-perigo">{escape(avarias)}</span>' if avarias else "Nenhuma",
                ),
            ]
        )
        + checklist
        + f'<div><div class="vist-secao">Fotos</div>{galeria}</div></div>'
    )
    return cartao_dados(titulo, corpo)


def _html_cartao_vazio(titulo, tipo):
    complemento = (
        " — será registrada no encerramento do contrato." if tipo == "devolucao" else "."
    )
    return (
        f'<div class="cartao cartao--tracejado"><h3 class="cartao__titulo texto-2">{titulo}</h3>'
        f'<div class="fs-secundario texto-2">Ainda não realizada{complemento}</div></div>'
    )


def _faixa_resumo(contrato, entrega, devolucao):
    periodo = f"{formatar_data(contrato['data_inicio'])} – " + (
        formatar_data(contrato["data_encerramento"]) if contrato.get("data_encerramento") else "em andamento"
    )
    rodados = km_rodados(entrega, devolucao)
    if devolucao is None:
        avarias, tom = "—", "texto-3"
    else:
        total = contar_avarias(devolucao)
        avarias, tom = (f"{total} registrada(s)", "perigo") if total else ("Nenhuma", None)
    faixa_dados(
        [
            ("Contrato", f'<span class="mono">{periodo}</span>'),
            ("Km rodados", f'<span class="mono">{_km(rodados)}</span>'),
            ("Avarias na devolução", avarias, tom),
        ]
    )


def _exibir_comparacao(contratos_por_id, frota, pessoas):
    contrato = contratos_por_id.get(st.session_state.get("vistorias_contrato"))
    moto = frota.get(contrato["moto_id"]) if contrato else None
    if not contrato or not moto:
        st.warning("Contrato não encontrado.")
        _voltar_lista()
        return

    if botao_voltar("vistorias", "voltar_vistorias"):
        _voltar_lista()

    cabecalho_ficha(
        ficha_identidade(
            escape(pessoas.get(contrato["cliente_id"], "—")),
            subtitulo=f'<span>{escape(moto["marca"])} {escape(moto["modelo"])}</span>',
            marca=chip_placa(moto["placa"], "grande"),
        )
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
    with paineis("vistorias_comparacao", iguais=True) as (painel_entrega, painel_devolucao):
        for painel, tipo, vistoria in [
            (painel_entrega, "entrega", entrega),
            (painel_devolucao, "devolucao", devolucao),
        ]:
            titulo = _TIPO_ROTULO[tipo]
            with painel:
                if not vistoria:
                    st.markdown(_html_cartao_vazio(titulo, tipo), unsafe_allow_html=True)
                    continue
                st.markdown(_html_cartao(titulo, vistoria, diferentes), unsafe_allow_html=True)
                if st.button(
                    "Adicionar fotos",
                    key=f"add_fotos_{vistoria['id']}",
                    icon=":material/add_a_photo:",
                    help=f"Anexar fotos à vistoria de {titulo.lower()}",
                ):
                    _dialog_fotos(vistoria)
    if diferentes:
        st.caption("Itens marcados como “alterado” (fundo amarelo) mudaram entre a entrega e a devolução.")


# ---------------------------------------------------------------- página --


def exibir():
    cabecalho("Vistorias", exibir_titulo=False)
    with proteger(nova_tentativa=True):
        frota = {m["id"]: m for m in motos.listar()}
        pessoas = {c["id"]: c["nome"] for c in clientes.listar()}
        contratos_por_id = {c["id"]: c for c in contratos.listar()}
        if st.session_state.get("vistorias_visao") == "comparacao":
            _exibir_comparacao(contratos_por_id, frota, pessoas)
        else:
            _exibir_lista(vistorias.listar(), contratos_por_id, frota, pessoas)
