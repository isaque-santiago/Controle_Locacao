"""Relatórios: resultado por moto, custos, inadimplência, fluxo de caixa."""

import streamlit as st
from decimal import Decimal

from src.services import relatorios, cobrancas, motos, clientes
from src.domain.valores import hoje_br
from src.ui.componentes import cabecalho, proteger, tabela

cabecalho("Relatórios")
with proteger():
    inicio = st.date_input("De", hoje_br().replace(day=1), format="DD/MM/YYYY")
    fim = st.date_input("Até", hoje_br(), format="DD/MM/YYYY")
    tipo = st.selectbox(
        "Relatório",
        [
            "Resultado por moto",
            "Custos por modelo",
            "Fluxo mensal",
            "Inadimplência atual",
        ],
    )
    dados = relatorios.resultado_por_moto(inicio, fim)
    if tipo == "Resultado por moto":
        linhas = dados["resultado"]
    elif tipo == "Fluxo mensal":
        linhas = dados["fluxo"]
    elif tipo == "Custos por modelo":
        grupos = {}
        for r in dados["resultado"]:
            grupos[r["modelo"]] = grupos.get(r["modelo"], 0) + r["custo_manutencao"]
        linhas = [
            {"modelo": modelo, "custo_manutencao": custo}
            for modelo, custo in grupos.items()
        ]
    else:
        st.caption(
            "Posição atual de cobranças em atraso, independente do período selecionado."
        )
        placas = {m["id"]: m["placa"] for m in motos.listar()}
        nomes = {c["id"]: c["nome"] for c in clientes.listar()}
        linhas = [
            {
                "placa": placas[c["moto_id"]],
                "cliente": nomes[c["cliente_id"]],
                "vencimento": c["vencimento"],
                "saldo": Decimal(str(c["saldo"])),
            }
            for c in cobrancas.listar()
            if c["situacao"] == "atrasada"
        ]
    st.caption(
        "Cauções não compõem receita. Manutenções são contabilizadas pela entrada, documentos pela regularização. Custo/km usa as leituras disponíveis no período; sem distância registrada, fica em branco."
    )
    tabela(linhas, "relatorio")
    if linhas:
        exportacao = [
            {k: v for k, v in r.items() if not k.endswith("_id")} for r in linhas
        ]
        st.download_button(
            "Exportar CSV",
            relatorios.exportar_csv(exportacao),
            "relatorio.csv",
            "text/csv",
        )
        st.download_button(
            "Exportar Excel",
            relatorios.exportar_excel(exportacao),
            "relatorio.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
