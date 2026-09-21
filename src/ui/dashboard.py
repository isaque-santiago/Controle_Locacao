"""Dashboard compartilhado pela página inicial e menu."""

import streamlit as st
from src.services import dashboard, alertas, cobrancas
from src.domain.valores import hoje_br
from src.ui.componentes import cabecalho, proteger, tabela
from src.ui.formatadores import formatar_moeda


def exibir():
    cabecalho("Visão geral da frota")
    with proteger():
        cobrancas.gerar_cobrancas_pendentes()
        dados = dashboard.resumo()
        frota = dados["frota"]
        colunas = st.columns(4)
        for coluna, status in zip(
            colunas, ["disponivel", "alugada", "manutencao", "inativa"]
        ):
            coluna.metric(
                status.capitalize(), sum(m["status"] == status for m in frota)
            )
        ativas = sum(m["status"] != "inativa" for m in frota)
        alugadas = sum(m["status"] == "alugada" for m in frota)
        st.metric(
            "Ocupação da frota ativa",
            f"{100 * alugadas / ativas:.1f}%" if ativas else "—",
        )
        if ativas:
            st.progress(alugadas / ativas)
        for coluna, (titulo, campo) in zip(
            st.columns(4),
            [
                ("Recebido no mês", "recebido"),
                ("Previsto no mês", "previsto"),
                ("Principal em atraso", "atrasado"),
                ("Manutenção no mês", "manutencao"),
            ],
        ):
            coluna.metric(titulo, formatar_moeda(dados[campo]))
        st.caption(
            "Receita exclui caução. Custos de manutenção usam a data de entrada dos serviços concluídos."
        )
        st.subheader("Hoje e atrasadas")
        placas = {m["id"]: m["placa"] for m in frota}
        tabela(
            [
                {**c, "placa": placas.get(c["moto_id"])}
                for c in dados["cobrancas"]
                if c["situacao"] == "atrasada"
                or (
                    c["situacao"] == "aberta"
                    and c["vencimento"] == hoje_br().isoformat()
                )
            ],
            "hoje",
        )
        st.subheader("Maiores devedores")
        tabela(dados["devedores"], "devedores")
        for titulo, registros in [
            ("Manutenção preventiva", alertas.listar_manutencao()),
            ("Documentos", alertas.listar_documentos()),
            ("CNHs", alertas.listar_cnh()),
        ]:
            st.subheader(titulo)
            tabela(
                [r for r in registros if r["situacao"] not in ("ok", "em_dia")], titulo
            )
