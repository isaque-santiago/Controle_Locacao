"""Documentos da moto: lista da frota, novo/editar e regularizar — segue Documentos.dc.html do mockup."""

from datetime import date
from html import escape

import streamlit as st

from src.services import documentos, motos, configuracoes
from src.domain.documentos import situacao_documento, sugerir_proximo_documento
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import (
    cabecalho,
    cabecalho_pagina,
    vazio_lista,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    botao_acao,
)
from src.ui.listas import barra_filtros, paginar, rodape_paginacao
from src.ui.registros import campo, lista_registros, registro
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
_EXTENSOES = ["pdf", "png", "jpg", "jpeg"]
_CHAVE_SUGESTAO = "documentos_sugestao"


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _mono(texto, estilo=""):
    return f'<span class="mono" style="font-size:var(--fs-secundario);{estilo}">{texto}</span>'


def _texto(texto, estilo=""):
    return f'<span style="font-size:var(--fs-secundario);{estilo}">{texto}</span>'


def _situacao(documento, hoje, alerta_dias):
    return situacao_documento(
        _data(documento["vencimento"]), documento["regularizado"], hoje, alerta_dias
    )


def _data(valor):
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


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
            "color:var(--texto-2);",
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
        chip_placa(moto["placa"]) + _texto(f" {escape(_TIPOS[documento['tipo']])}", "color:var(--texto-2);"),
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

def _tabela(visiveis, frota, hoje, alerta_dias, total):
    pagina_atual, pagina = paginar("documentos", visiveis)
    with lista_registros("documentos", acoes=3):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhum documento encontrado.", "Ainda não há documentos cadastrados.", total > 0, "Novo documento"),
                unsafe_allow_html=True,
            )
        for doc in pagina_atual:
            moto = frota.get(doc["moto_id"])
            situacao = _situacao(doc, hoje, alerta_dias)
            rotulo_situacao = "Regularizado" if doc["regularizado"] else _SITUACAO_ROTULO[situacao]
            referencia = doc.get("descricao") or doc.get("ano_referencia") or "—"
            tipo_doc = _TIPOS.get(doc["tipo"], doc["tipo"])
            campos = [
                campo("Tipo", _texto(escape(tipo_doc))),
                campo("Referência", _texto(escape(str(referencia)), "color:var(--texto-2);")),
                campo("Vencimento", _mono(formatar_data(doc["vencimento"]))),
                campo("Valor", _mono(formatar_moeda(doc["valor"]) if doc.get("valor") is not None else "—")),
            ]
            with registro(
                "documentos",
                doc["id"],
                chip_placa(moto["placa"]) if moto else "—",
                campos,
                selo=selo_situacao(rotulo_situacao, "em_dia" if doc["regularizado"] else situacao),
            ) as acoes:
                if botao_acao(
                    acoes,
                    "comprovante",
                    f"comprovante_doc_{doc['id']}",
                    ajuda=f"Ver o comprovante do {tipo_doc}" if doc.get("arquivo_path") else "Sem comprovante anexado",
                    desabilitado=not doc.get("arquivo_path") or not moto,
                ):
                    _dialog_comprovante(doc, moto)
                if botao_acao(acoes, "editar", f"editar_doc_{doc['id']}", ajuda=f"Editar o documento {tipo_doc}"):
                    _dialog_editar(doc)
                if not doc["regularizado"] and moto:
                    if botao_acao(
                        acoes,
                        "regularizar",
                        f"regularizar_doc_{doc['id']}",
                        ajuda=f"Marcar o documento {tipo_doc} como regularizado",
                    ):
                        _dialog_regularizar(doc, moto)
    rodape_paginacao("documentos", pagina)


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

        if cabecalho_pagina(
            "Documentos",
            sub=f"{vencidos} vencido(s) · {a_vencer} a vencer",
            acao={"rotulo": "Novo documento", "chave": "documentos_novo"},
        ):
            _dialog_novo({})

        contagem = {
            "todos": len(todos),
            "vencido": vencidos,
            "a_vencer": a_vencer,
            "em_dia": len(todos) - vencidos - a_vencer,
        }
        filtros = barra_filtros(
            "documentos",
            _FILTROS,
            padrao="todos",
            contagens=contagem,
            busca="Buscar por placa",
        )
        busca = filtros.busca.casefold().replace("-", "")

        visiveis = [
            d
            for d in todos
            if (filtros.valor == "todos" or situacoes[d["id"]] == filtros.valor)
            and busca in frota.get(d["moto_id"], {}).get("placa", "").casefold()
        ]
        visiveis.sort(
            key=lambda d: (_ORDEM_SITUACAO[situacoes[d["id"]]], d["regularizado"], str(d["vencimento"]))
        )
        filtros.resumo(len(visiveis), ("documento", "documentos"))
        st.write("")
        _tabela(visiveis, frota, hoje, alerta_dias, len(todos))

        # Sugestão do ano seguinte, deixada pela regularização anterior.
        if sugestao := st.session_state.pop(_CHAVE_SUGESTAO, None):
            _dialog_novo(sugestao)
