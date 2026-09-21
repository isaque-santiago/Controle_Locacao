"""Vistorias de entrega e devolução, com checklist e fotos."""

import streamlit as st

from src.services import vistorias, contratos, motos, clientes
from src.ui.componentes import cabecalho, proteger, selecionar, tabela, sucesso
from src.ui.vistorias import campos, preparar

cabecalho("Vistorias")
with proteger():
    frota = {m["id"]: m for m in motos.listar()}
    pessoas = {c["id"]: c["nome"] for c in clientes.listar()}
    contrato = selecionar(
        "Contrato",
        contratos.listar(),
        lambda c: f"{frota[c['moto_id']]['placa']} • {pessoas[c['cliente_id']]} • {c['data_inicio']}",
        "vist_contrato",
    )
    if contrato:
        registros = vistorias.listar_por_contrato(contrato["id"])
        tabela(registros, "vistorias")
        faltantes = [
            t
            for t in ("entrega", "devolucao")
            if t not in [v["tipo"] for v in registros]
        ]
        if faltantes:
            tipo = st.selectbox("Tipo de vistoria", faltantes)
            with st.form("vistoria_" + contrato["id"] + tipo):
                dados = campos("avulsa", frota[contrato["moto_id"]]["km_atual"])
                if st.form_submit_button("Registrar vistoria", type="primary"):
                    vistorias.registrar_vistoria(
                        contrato["id"], contrato["moto_id"], tipo, **preparar(dados)
                    )
                    sucesso()
        vistoria = selecionar(
            "Vistoria para fotos", registros, lambda v: v["tipo"], "fotos_vistoria"
        )
        if vistoria:
            fotos = st.file_uploader(
                "Fotos", type=["jpg", "jpeg", "png"], accept_multiple_files=True
            )
            if fotos and st.button("Salvar fotos"):
                for foto in fotos:
                    vistorias.anexar_foto(
                        vistoria["id"], foto.name, foto.getvalue(), foto.type
                    )
                sucesso()
            for foto in vistoria.get("fotos", []):
                st.image(
                    vistorias.url_foto(foto["storage_path"]),
                    caption=foto.get("legenda") or "Foto da vistoria",
                    width=350,
                )
        st.subheader("Comparação entrega × devolução")
        comparacao = vistorias.comparar_entrega_devolucao(contrato["id"])
        if comparacao["diferencas"] is None:
            st.info("Registre as duas vistorias para comparar os itens.")
        elif not comparacao["diferencas"]:
            st.success("Nenhuma diferença nos checklists.")
        else:
            tabela(
                [{"item": k, **v} for k, v in comparacao["diferencas"].items()],
                "comparacao",
            )
