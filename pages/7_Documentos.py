"""Documentos da moto: IPVA, licenciamento, seguro."""

import streamlit as st

from src.services import documentos, motos, alertas
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import (
    cabecalho,
    proteger,
    selecionar,
    tabela,
    campo_data,
    sucesso,
)

cabecalho("Documentos")
with proteger():
    tabela(alertas.listar_documentos(), "alertas_doc")
    moto = selecionar("Moto", motos.listar(), lambda m: m["placa"], "doc_moto")
    if moto:
        registros = documentos.listar_por_moto(moto["id"])
        tabela(registros, "documentos")
        modo = st.radio("Documento", ["Novo documento", "Editar documento"])
        sugestao = st.session_state.get("sugestao_documento", {})
        if sugestao.get("moto_id") != moto["id"]:
            sugestao = {}
        doc = (
            sugestao
            if modo == "Novo documento"
            else selecionar(
                "Documento existente",
                registros,
                lambda d: f"{d['tipo']} • {d.get('ano_referencia') or ''} • {d['vencimento']}",
                "editar_doc",
            )
        )
        if doc is not None:
            with st.form(
                "doc_" + doc.get("id", "novo") + str(doc.get("ano_referencia", ""))
            ):
                tipos = ["ipva", "licenciamento", "seguro", "vistoria_detran", "outro"]
                tipo = st.selectbox(
                    "Tipo", tipos, index=tipos.index(doc.get("tipo", "ipva"))
                )
                ano = st.number_input(
                    "Ano de referência",
                    min_value=1900,
                    max_value=2100,
                    value=doc.get("ano_referencia") or hoje_br().year,
                )
                vencimento = campo_data("Vencimento", doc.get("vencimento"))
                descricao = st.text_input("Descrição", doc.get("descricao") or "")
                valor = st.text_input("Valor (R$)", str(doc.get("valor") or "0"))
                if st.form_submit_button("Salvar documento", type="primary"):
                    if not vencimento:
                        raise ValueError("Informe o vencimento do documento.")
                    dados = {
                        "moto_id": moto["id"],
                        "tipo": tipo,
                        "ano_referencia": ano,
                        "vencimento": vencimento.isoformat(),
                        "descricao": descricao,
                        "valor": str(decimal_br(valor)),
                    }
                    if doc.get("id"):
                        documentos.atualizar(doc["id"], dados)
                    else:
                        documentos.criar(dados)
                        st.session_state.pop("sugestao_documento", None)
                    sucesso()
            if doc.get("id"):
                arquivo = st.file_uploader(
                    "Comprovante (PDF ou imagem)", type=["pdf", "png", "jpg", "jpeg"]
                )
                if arquivo and st.button("Anexar comprovante"):
                    documentos.anexar_comprovante(
                        doc["id"],
                        moto["id"],
                        arquivo.name,
                        arquivo.getvalue(),
                        arquivo.type,
                    )
                    sucesso()
                if doc.get("arquivo_path") and st.button("Abrir comprovante"):
                    st.link_button(
                        "Ver comprovante (válido por 5 minutos)",
                        documentos.url_comprovante(doc["arquivo_path"]),
                    )
                if not doc["regularizado"]:
                    data = st.date_input(
                        "Data de regularização", hoje_br(), format="DD/MM/YYYY"
                    )
                    if st.button("Marcar como regularizado"):
                        resultado = documentos.regularizar(doc["id"], data)
                        if resultado["sugestao_proximo"]:
                            st.session_state["sugestao_documento"] = {
                                **resultado["sugestao_proximo"],
                                "moto_id": moto["id"],
                            }
                        sucesso()
        if sugestao:
            st.info(
                "O documento do próximo ano está sugerido em Novo documento. Preencha o vencimento e salve para criá-lo."
            )
