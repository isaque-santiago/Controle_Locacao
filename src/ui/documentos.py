"""Documentos da moto: lista da frota, novo/editar e regularizar — segue Documentos.dc.html do mockup."""

from datetime import date
from html import escape

import streamlit as st

from src.services import documentos, motos, configuracoes
from src.domain.documentos import situacao_documento, sugerir_proximo_documento
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import (
    cabecalho,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
)
from src.ui.formatadores import formatar_data, formatar_moeda, formatar_placa

_TIPOS = {
    "ipva": "IPVA",
    "licenciamento": "Licenciamento",
    "seguro": "Seguro",
    "vistoria_detran": "Vistoria Detran",
    "outro": "Outro",
}
_SITUACAO_ROTULO = {"vencido": "Vencido", "a_vencer": "A vencer", "em_dia": "Em dia"}
_ORDEM_SITUACAO = {"vencido": 0, "a_vencer": 1, "em_dia": 2}
_FILTROS = [
    ("todos", "Todos"),
    ("vencido", "Vencido"),
    ("a_vencer", "A vencer"),
    ("em_dia", "Em dia"),
]
_POR_PAGINA = 10
_EXTENSOES = ["pdf", "png", "jpg", "jpeg"]
_CHAVE_SUGESTAO = "documentos_sugestao"


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _mono(texto, estilo=""):
    return f'<span class="mono" style="font-size:13px;{estilo}">{texto}</span>'


def _texto(texto, estilo=""):
    return f'<span style="font-size:13px;{estilo}">{texto}</span>'


def _cabecalho_tabela(colunas, rotulos):
    for coluna, rotulo in zip(colunas, rotulos):
        coluna.markdown(
            f'<span style="font-size:13px;color:#585F66;">{rotulo}</span>',
            unsafe_allow_html=True,
        )


def _situacao(documento, hoje, alerta_dias):
    return situacao_documento(
        _data(documento["vencimento"]), documento["regularizado"], hoje, alerta_dias
    )


def _data(valor):
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def _pills(opcoes, contagens):
    """Filtros em pílula (mesmo padrão de Motos/Clientes/Contratos). Devolve o valor ativo."""
    atual = st.session_state.get("documentos_filtro", "todos")
    with st.container(key="documentos_filtros"):
        colunas = st.columns(len(opcoes))
        for coluna, (valor, rotulo) in zip(colunas, opcoes):
            if coluna.button(
                f"{rotulo} · {contagens[valor]}",
                key=f"pill_doc_{valor}",
                type="primary" if atual == valor else "secondary",
                use_container_width=True,
            ):
                st.session_state["documentos_filtro"] = valor
                st.session_state["documentos_pagina"] = 1
                st.rerun()
    return atual


def _paginar(registros):
    total_paginas = max(1, -(-len(registros) // _POR_PAGINA))
    pagina = min(st.session_state.get("documentos_pagina", 1), total_paginas)
    inicio = (pagina - 1) * _POR_PAGINA
    return registros[inicio : inicio + _POR_PAGINA], pagina, total_paginas


def _rodape_paginacao(exibidos, total, pagina, total_paginas):
    if total_paginas <= 1:
        return
    st.caption(f"Mostrando {exibidos} de {total} · página {pagina} de {total_paginas}")
    anterior, proxima = st.columns(2)
    if anterior.button("‹ Anterior", disabled=pagina <= 1, key="doc_ant"):
        st.session_state["documentos_pagina"] = pagina - 1
        st.rerun()
    if proxima.button("Próxima ›", disabled=pagina >= total_paginas, key="doc_prox"):
        st.session_state["documentos_pagina"] = pagina + 1
        st.rerun()


# ---------------------------------------------------------------- diálogos --

def _anexar(documento_id, moto_id, arquivo):
    documentos.anexar_comprovante(
        documento_id, moto_id, arquivo.name, arquivo.getvalue(), arquivo.type
    )


def _dialogo_documento(documento):
    """Formulário único de novo/editar documento. `documento` vazio = novo; com
    `id` = edição; sem `id` mas com dados = sugestão do ano seguinte."""
    editando = bool(documento.get("id"))
    frota = [m for m in motos.listar() if m["status"] != "inativa" or m["id"] == documento.get("moto_id")]
    if not frota:
        st.info("Cadastre uma moto antes de registrar documentos.")
        return
    ids = [m["id"] for m in frota]
    padrao = documento.get("moto_id")
    tipos = list(_TIPOS)

    with st.form("form_documento_" + str(documento.get("id", "novo"))):
        moto_id = st.selectbox(
            "Moto",
            ids,
            index=ids.index(padrao) if padrao in ids else 0,
            format_func=lambda i: next(
                f"{formatar_placa(m['placa'])} · {m['marca']} {m['modelo']}" for m in frota if m["id"] == i
            ),
            disabled=editando,
        )
        tipo = st.radio(
            "Tipo",
            tipos,
            index=tipos.index(documento.get("tipo", "ipva")),
            format_func=_TIPOS.get,
            horizontal=True,
        )
        col_ano, col_venc = st.columns([1, 2])
        ano = col_ano.number_input(
            "Ano de referência",
            min_value=1900,
            max_value=2100,
            value=documento.get("ano_referencia") or hoje_br().year,
            step=1,
        )
        with col_venc:
            vencimento = campo_data("Vencimento", documento.get("vencimento"))
        col_valor, col_desc = st.columns([1, 2])
        valor = col_valor.text_input(
            "Valor (R$)", str(documento.get("valor") or "0").replace(".", ",")
        )
        descricao = col_desc.text_input(
            "Descrição (ex.: apólice 221004)", documento.get("descricao") or ""
        )
        arquivo = st.file_uploader(
            "Comprovante (opcional) — PDF ou imagem", type=_EXTENSOES, key="documento_arquivo"
        )
        if editando and documento.get("arquivo_path") and not arquivo:
            st.caption("Já existe um comprovante anexado; enviar outro arquivo o substitui.")
        observacoes = st.text_area(
            "Observações", documento.get("observacoes") or "", height=68
        )
        col_cancelar, col_salvar = st.columns(2)
        cancelar = col_cancelar.form_submit_button("Cancelar", use_container_width=True)
        salvar = col_salvar.form_submit_button(
            "Salvar documento", type="primary", use_container_width=True
        )
        if cancelar:
            st.rerun()
        if salvar:
            with proteger():
                if not vencimento:
                    raise ValueError("Informe o vencimento do documento.")
                dados = {
                    "moto_id": moto_id,
                    "tipo": tipo,
                    "ano_referencia": int(ano),
                    "vencimento": vencimento.isoformat(),
                    "descricao": descricao.strip() or None,
                    "valor": str(decimal_br(valor)),
                    "observacoes": observacoes.strip() or None,
                }
                if editando:
                    salvo = documentos.atualizar(documento["id"], dados)
                else:
                    salvo = documentos.criar(dados)
                if arquivo:
                    _anexar(salvo["id"], moto_id, arquivo)
                _salvo("Documento salvo.")


@st.dialog("Novo documento", width="large")
def _dialog_novo(sugestao):
    _dialogo_documento(sugestao)


@st.dialog("Editar documento", width="large")
def _dialog_editar(documento):
    _dialogo_documento(documento)


@st.dialog("Marcar como regularizado")
def _dialog_regularizar(documento, moto):
    rotulo = _TIPOS[documento["tipo"]]
    referencia = documento.get("ano_referencia") or documento.get("descricao") or ""
    st.markdown(
        chip_placa(moto["placa"])
        + _texto(
            f" {escape(rotulo)} {escape(str(referencia))} · vence {formatar_data(documento['vencimento'])}",
            "color:#585F66;",
        ),
        unsafe_allow_html=True,
    )
    with st.form("form_regularizar_" + documento["id"]):
        data = st.date_input("Data de regularização", hoje_br(), format="DD/MM/YYYY")
        arquivo = st.file_uploader("Comprovante", type=_EXTENSOES, key="regularizar_arquivo")
        proximo = sugerir_proximo_documento(documento["tipo"], documento.get("ano_referencia"))
        criar_proximo = False
        if proximo:
            criar_proximo = st.checkbox(
                f"Cadastrar em seguida o documento de {proximo['ano_referencia']}",
                value=True,
                help="Abre o cadastro já preenchido, com o vencimento em branco para você informar.",
            )
        col_cancelar, col_confirmar = st.columns(2)
        cancelar = col_cancelar.form_submit_button("Cancelar", use_container_width=True)
        confirmar = col_confirmar.form_submit_button(
            "Confirmar", type="primary", use_container_width=True
        )
        if cancelar:
            st.rerun()
        if confirmar:
            with proteger():
                if arquivo:
                    _anexar(documento["id"], documento["moto_id"], arquivo)
                resultado = documentos.regularizar(documento["id"], data or hoje_br())
                if criar_proximo and resultado["sugestao_proximo"]:
                    st.session_state[_CHAVE_SUGESTAO] = {
                        **resultado["sugestao_proximo"],
                        "moto_id": documento["moto_id"],
                    }
                _salvo("Documento regularizado.")


@st.dialog("Comprovante")
def _dialog_comprovante(documento, moto):
    st.markdown(
        chip_placa(moto["placa"]) + _texto(f" {escape(_TIPOS[documento['tipo']])}", "color:#585F66;"),
        unsafe_allow_html=True,
    )
    with proteger():
        st.link_button(
            "Abrir comprovante (link válido por 5 minutos)",
            documentos.url_comprovante(documento["arquivo_path"]),
            type="primary",
            use_container_width=True,
        )


# ---------------------------------------------------------------- listagem --

def _tabela(visiveis, frota, hoje, alerta_dias):
    pagina_atual, pagina, total_paginas = _paginar(visiveis)
    larguras = [1.3, 1.4, 1.5, 1.2, 1.2, 1.2, 0.4, 0.4, 0.4]
    with st.container(key="documentos_card_lista"):
        _cabecalho_tabela(
            st.columns(larguras, vertical_alignment="center"),
            ["Moto", "Tipo", "Referência", "Vencimento", "Valor", "Situação", "", "", ""],
        )
        if not pagina_atual:
            st.markdown(
                '<div style="padding:16px 20px;color:#585F66;font-size:13px;">'
                "Nenhum documento encontrado.</div>",
                unsafe_allow_html=True,
            )
        for doc in pagina_atual:
            moto = frota.get(doc["moto_id"])
            situacao = _situacao(doc, hoje, alerta_dias)
            rotulo_situacao = "Regularizado" if doc["regularizado"] else _SITUACAO_ROTULO[situacao]
            referencia = doc.get("descricao") or doc.get("ano_referencia") or "—"
            linha = st.columns(larguras, vertical_alignment="center")
            linha[0].markdown(chip_placa(moto["placa"]) if moto else "—", unsafe_allow_html=True)
            linha[1].markdown(_texto(_TIPOS.get(doc["tipo"], doc["tipo"])), unsafe_allow_html=True)
            linha[2].markdown(_texto(escape(str(referencia)), "color:#585F66;"), unsafe_allow_html=True)
            linha[3].markdown(_mono(formatar_data(doc["vencimento"])), unsafe_allow_html=True)
            linha[4].markdown(
                _mono(
                    formatar_moeda(doc["valor"]) if doc.get("valor") is not None else "—",
                    "text-align:right;display:block;",
                ),
                unsafe_allow_html=True,
            )
            linha[5].markdown(
                selo_situacao(rotulo_situacao, "em_dia" if doc["regularizado"] else situacao),
                unsafe_allow_html=True,
            )
            if linha[6].button(
                "↗",
                key=f"comprovante_doc_{doc['id']}",
                help="Ver comprovante" if doc.get("arquivo_path") else "Sem comprovante anexado",
                disabled=not doc.get("arquivo_path") or not moto,
            ):
                _dialog_comprovante(doc, moto)
            if linha[7].button("✎", key=f"editar_doc_{doc['id']}", help="Editar documento"):
                _dialog_editar(doc)
            if not doc["regularizado"] and moto:
                if linha[8].button("✓", key=f"regularizar_doc_{doc['id']}", help="Marcar como regularizado"):
                    _dialog_regularizar(doc, moto)
    _rodape_paginacao(len(pagina_atual), len(visiveis), pagina, total_paginas)


# ---------------------------------------------------------------- página --

def exibir():
    cabecalho("Documentos", exibir_titulo=False)
    with proteger():
        frota = {m["id"]: m for m in motos.listar()}
        alerta_dias = int(configuracoes.obter()["alerta_documento_dias"])
        hoje = hoje_br()
        todos = documentos.listar_todos()
        situacoes = {d["id"]: _situacao(d, hoje, alerta_dias) for d in todos}
        vencidos = sum(s == "vencido" for s in situacoes.values())
        a_vencer = sum(s == "a_vencer" for s in situacoes.values())

        col_titulo, col_botao = st.columns([5, 1.4], vertical_alignment="center")
        col_titulo.markdown(
            f"""
            <h1 class="rotulo" style="margin:0;font-size:28px;color:#1E2227;">Documentos</h1>
            <div style="color:#585F66;font-size:13px;margin-top:2px;">{vencidos} vencido(s) · {a_vencer} a vencer</div>
            """,
            unsafe_allow_html=True,
        )
        with col_botao:
            if st.button("+ Novo documento", type="primary", use_container_width=True):
                _dialog_novo({})

        contagem = {
            "todos": len(todos),
            "vencido": vencidos,
            "a_vencer": a_vencer,
            "em_dia": len(todos) - vencidos - a_vencer,
        }
        col_pills, col_busca = st.columns([3, 1.3], vertical_alignment="center")
        with col_pills:
            filtro = _pills(_FILTROS, contagem)
        with col_busca:
            busca = (
                st.text_input(
                    "Buscar",
                    placeholder="Buscar por placa",
                    label_visibility="collapsed",
                    key="documentos_busca",
                )
                .casefold()
                .replace("-", "")
            )

        visiveis = [
            d
            for d in todos
            if (filtro == "todos" or situacoes[d["id"]] == filtro)
            and busca in frota.get(d["moto_id"], {}).get("placa", "").casefold()
        ]
        visiveis.sort(
            key=lambda d: (_ORDEM_SITUACAO[situacoes[d["id"]]], d["regularizado"], str(d["vencimento"]))
        )
        st.write("")
        _tabela(visiveis, frota, hoje, alerta_dias)

        # Sugestão do ano seguinte, deixada pela regularização anterior.
        if sugestao := st.session_state.pop(_CHAVE_SUGESTAO, None):
            _dialog_novo(sugestao)
