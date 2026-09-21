"""Cadastro e ficha das motos da frota."""

import streamlit as st

from src.services import motos, manutencao, documentos, contratos, relatorios
from datetime import date
from src.domain.valores import hoje_br
from src.domain.valores import decimal_br
from src.ui.componentes import (
    cabecalho,
    proteger,
    selecionar,
    tabela,
    campo_data,
    sucesso,
)

cabecalho("Motos")
with proteger():
    registros = motos.listar()
    busca = st.text_input("Buscar por placa, marca ou modelo")
    situacao = st.selectbox(
        "Situação", ["Todas", "disponivel", "alugada", "manutencao", "inativa"]
    )
    tabela(
        [
            m
            for m in registros
            if busca.casefold() in f"{m['placa']} {m['marca']} {m['modelo']}".casefold()
            and (situacao == "Todas" or m["status"] == situacao)
        ],
        "motos",
        ["placa", "marca", "modelo", "km_atual", "status"],
    )
    modo = st.radio("Cadastro", ["Nova moto", "Editar moto"], horizontal=True)
    moto = (
        {}
        if modo == "Nova moto"
        else selecionar(
            "Moto", registros, lambda m: f"{m['placa']} • {m['modelo']}", "editar_moto"
        )
    )
    if moto is not None:
        with st.form("moto_" + moto.get("id", "nova")):
            dados = {}
            for campo, titulo in [
                ("placa", "Placa"),
                ("marca", "Marca"),
                ("modelo", "Modelo"),
                ("renavam", "Renavam"),
                ("chassi", "Chassi"),
                ("cor", "Cor"),
            ]:
                dados[campo] = st.text_input(titulo, value=moto.get(campo) or "")
            for campo in ("ano_fabricacao", "ano_modelo"):
                dados[campo] = st.number_input(
                    campo.replace("_", " ").capitalize(),
                    min_value=1900,
                    max_value=2100,
                    value=moto.get(campo) or 2026,
                )
            if not moto:
                dados["km_atual"] = st.number_input(
                    "Quilometragem inicial", min_value=0, step=1
                )
            aquisicao = st.text_input(
                "Valor de aquisição (R$)", str(moto.get("valor_aquisicao") or "0")
            )
            locacao = st.text_input(
                "Locação sugerida (R$)", str(moto.get("valor_locacao_sugerido") or "0")
            )
            data = campo_data("Data de aquisição", moto.get("data_aquisicao"))
            dados["data_aquisicao"] = data.isoformat() if data else None
            dados["observacoes"] = st.text_area(
                "Observações", moto.get("observacoes") or ""
            )
            if st.form_submit_button("Salvar moto", type="primary"):
                dados.update(
                    valor_aquisicao=str(decimal_br(aquisicao)),
                    valor_locacao_sugerido=str(decimal_br(locacao)),
                )
                if moto:
                    motos.atualizar(moto["id"], dados)
                else:
                    motos.criar(dados)
                sucesso()
        if moto:
            historicos = st.tabs(["Serviços", "Documentos", "Contratos", "Financeiro"])
            with historicos[0]:
                tabela(manutencao.listar_manutencoes(moto["id"]), "moto_servicos")
            with historicos[1]:
                tabela(documentos.listar_por_moto(moto["id"]), "moto_documentos")
            with historicos[2]:
                tabela(
                    [c for c in contratos.listar() if c["moto_id"] == moto["id"]],
                    "moto_contratos",
                )
            with historicos[3]:
                tabela(
                    [
                        r
                        for r in relatorios.resultado_por_moto(
                            date(1900, 1, 1), hoje_br()
                        )["resultado"]
                        if r["moto_id"] == moto["id"]
                    ],
                    "moto_financeiro",
                )
            st.subheader("Quilometragem")
            st.metric("Km atual", moto["km_atual"])
            with st.form("atualizar_km"):
                km = st.number_input(
                    "Nova leitura", min_value=0, value=moto["km_atual"], step=1
                )
                confirmar = st.checkbox(
                    "Confirmo o lançamento de uma leitura histórica menor (o km atual será mantido)"
                )
                if st.form_submit_button("Registrar leitura"):
                    motos.atualizar_km(moto["id"], km, confirmar_km_menor=confirmar)
                    sucesso()
            tabela(motos.historico(moto["id"]), "historico_km")
            st.subheader("Plano preventivo")
            plano = manutencao.listar_plano_moto(moto["id"])
            tabela(
                [
                    {
                        **p,
                        "item_nome": p["item"]["nome"],
                        "situacao": manutencao.situacao_item_plano(p, moto["km_atual"]),
                    }
                    for p in plano
                ],
                "plano",
            )
            if st.button("Aplicar itens ativos do catálogo"):
                manutencao.aplicar_plano_padrao(moto["id"])
                sucesso()
            item = selecionar(
                "Item do plano", plano, lambda p: p["item"]["nome"], "item_plano"
            )
            if item:
                with st.form("ajuste_plano_" + item["id"]):
                    intervalo_km = st.number_input(
                        "Intervalo em km (0 usa catálogo)",
                        min_value=0,
                        value=item["intervalo_km"] or 0,
                    )
                    intervalo_dias = st.number_input(
                        "Intervalo em dias (0 usa catálogo)",
                        min_value=0,
                        value=item["intervalo_dias"] or 0,
                    )
                    ultima_km = st.number_input(
                        "Km da última manutenção",
                        min_value=0,
                        value=item["ultima_km"] or 0,
                    )
                    ultima_data = campo_data(
                        "Data da última manutenção", item["ultima_data"]
                    )
                    if st.form_submit_button("Salvar plano"):
                        manutencao.atualizar_plano(
                            item["id"],
                            {
                                "intervalo_km": intervalo_km or None,
                                "intervalo_dias": intervalo_dias or None,
                                "ultima_km": ultima_km,
                                "ultima_data": (
                                    ultima_data.isoformat() if ultima_data else None
                                ),
                            },
                        )
                        sucesso()
            if moto["status"] in ("disponivel", "inativa") and st.button(
                "Reativar moto" if moto["status"] == "inativa" else "Inativar moto"
            ):
                motos.atualizar(
                    moto["id"],
                    {
                        "status": (
                            "disponivel" if moto["status"] == "inativa" else "inativa"
                        )
                    },
                )
                sucesso()
