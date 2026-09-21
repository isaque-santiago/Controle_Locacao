"""Criação, ficha e encerramento de contratos."""

import streamlit as st

from datetime import timedelta
from src.services import contratos, motos, clientes, cobrancas, vistorias, manutencao
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import cabecalho, proteger, selecionar, tabela, sucesso
from src.ui.vistorias import campos, preparar

cabecalho("Contratos")
with proteger():
    frota, pessoas, registros = motos.listar(), clientes.listar(), contratos.listar()
    placas = {m["id"]: m["placa"] for m in frota}
    nomes = {c["id"]: c["nome"] for c in pessoas}
    rotulo = (
        lambda c: f"{placas.get(c['moto_id'], '')} • {nomes.get(c['cliente_id'], '')} • {c['data_inicio']}"
    )
    filtro = st.selectbox("Situação", ["Todos", "ativo", "encerrado", "cancelado"])
    tabela(
        [
            {
                **c,
                "placa": placas.get(c["moto_id"]),
                "cliente": nomes.get(c["cliente_id"]),
            }
            for c in registros
            if filtro == "Todos" or c["status"] == filtro
        ],
        "contratos",
    )
    novo, ficha = st.tabs(["Novo contrato", "Ficha e encerramento"])
    with novo:
        moto = selecionar(
            "Moto disponível",
            [m for m in frota if m["status"] == "disponivel"],
            lambda m: m["placa"],
            "contrato_moto",
        )
        cliente = selecionar(
            "Cliente ativo",
            [c for c in pessoas if c["status"] == "ativo"],
            lambda c: c["nome"],
            "contrato_cliente",
        )
        if moto and cliente:
            atrasadas = [
                c
                for c in cobrancas.listar()
                if c["cliente_id"] == cliente["id"] and c["situacao"] == "atrasada"
            ]
            if atrasadas:
                st.warning(
                    "Este cliente possui cobranças em atraso. Confira a página Cobranças antes de contratar."
                )
            inicio = st.date_input("Início", hoje_br(), format="DD/MM/YYYY")
            fim = st.date_input(
                "Fim previsto", hoje_br() + timedelta(days=30), format="DD/MM/YYYY"
            )
            periodicidade = st.selectbox(
                "Periodicidade", ["diario", "semanal", "quinzenal", "mensal"]
            )
            valor = st.text_input(
                "Valor do período (R$)", str(moto.get("valor_locacao_sugerido") or "0")
            )
            caucao = st.text_input("Caução (R$)", "0")
            if st.button("Ver agenda antes de contratar"):
                tabela(
                    contratos.previa_agenda(
                        inicio, periodicidade, decimal_br(valor, positivo=True), fim
                    ),
                    "previa",
                )
            st.subheader("Vistoria de entrega")
            with st.form("novo_contrato_" + moto["id"]):
                vistoria = campos("entrega", moto["km_atual"])
                if st.form_submit_button(
                    "Criar contrato e registrar entrega", type="primary"
                ):
                    dados_vistoria = preparar(vistoria)
                    contratos.criar_com_vistoria(
                        {
                            "moto_id": moto["id"],
                            "cliente_id": cliente["id"],
                            "data_inicio": inicio.isoformat(),
                            "data_fim_prevista": fim.isoformat(),
                            "periodicidade": periodicidade,
                            "valor_periodo": str(decimal_br(valor, positivo=True)),
                            "caucao_valor": str(decimal_br(caucao)),
                            "km_inicial": dados_vistoria["km"],
                        },
                        dados_vistoria,
                    )
                    sucesso()
            st.caption("Após salvar, anexe as fotos na página Vistorias.")
    with ficha:
        contrato = selecionar("Contrato", registros, rotulo, "ficha_contrato")
        if contrato:
            tabela(cobrancas.listar_por_contrato(contrato["id"]), "parcelas_contrato")
            tabela(vistorias.listar_por_contrato(contrato["id"]), "vistorias_contrato")
            diferencas = vistorias.comparar_entrega_devolucao(contrato["id"])[
                "diferencas"
            ]
            if diferencas is not None:
                tabela(
                    [{"item": k, **v} for k, v in diferencas.items()],
                    "contrato_comparacao",
                )
            tabela(
                [
                    m
                    for m in manutencao.listar_manutencoes(contrato["moto_id"])
                    if contrato["data_inicio"]
                    <= m["data_entrada"]
                    <= (contrato.get("data_encerramento") or hoje_br().isoformat())
                ],
                "contrato_servicos",
            )
            if contrato["status"] == "ativo":
                st.subheader("Encerramento e vistoria de devolução")
                moto_atual = next(m for m in frota if m["id"] == contrato["moto_id"])
                with st.form("encerramento_" + contrato["id"]):
                    data = st.date_input(
                        "Data do encerramento", hoje_br(), format="DD/MM/YYYY"
                    )
                    devolvida = st.checkbox("Caução devolvida")
                    vistoria = campos("devolucao", moto_atual["km_atual"])
                    if st.form_submit_button("Encerrar contrato e registrar devolução"):
                        contratos.encerrar_com_vistoria(
                            contrato["id"], data, preparar(vistoria), devolvida
                        )
                        sucesso()
