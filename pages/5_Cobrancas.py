"""Cobranças: hoje, atrasadas, próximas e pagas; registro de pagamento."""

import streamlit as st

from datetime import date, timedelta
from src.services import cobrancas, motos, clientes
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import cabecalho, proteger, selecionar, tabela, sucesso
from src.ui.formatadores import formatar_moeda, formatar_data

cabecalho("Cobranças")
with proteger():
    cobranca_rapida = st.session_state.pop("cobranca_rapida", None)
    registros = cobrancas.listar()
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    filtro = st.selectbox(
        "Exibir",
        ["Em aberto", "Hoje", "Atrasadas", "Próximos 7 dias", "Pagas", "Todas"],
    )

    def incluir(c):
        aberta = c["situacao"] in ("aberta", "atrasada")
        vencimento = date.fromisoformat(c["vencimento"])
        return {
            "Em aberto": aberta,
            "Hoje": aberta and vencimento == hoje_br(),
            "Atrasadas": c["situacao"] == "atrasada",
            "Próximos 7 dias": aberta
            and hoje_br() < vencimento <= hoje_br() + timedelta(days=7),
            "Pagas": c["situacao"] == "paga",
            "Todas": True,
        }[filtro]

    linhas = [
        {**c, "placa": placas.get(c["moto_id"]), "cliente": nomes.get(c["cliente_id"])}
        for c in registros
        if incluir(c)
    ]
    tabela(linhas, "cobrancas")
    if cobranca_rapida and any(l["id"] == cobranca_rapida for l in linhas):
        st.session_state["receber"] = cobranca_rapida
    cobranca = selecionar(
        "Cobrança para consultar ou receber",
        linhas,
        lambda c: f"{c['placa']} • {c['cliente']} • {formatar_data(c['vencimento'])} • {c['tipo']} • saldo {formatar_moeda(c['saldo'])}",
        "receber",
    )
    if cobranca:
        st.caption("Mensagem para copiar e enviar ao cliente")
        st.code(
            f"Olá, {cobranca['cliente']}. A cobrança de {formatar_data(cobranca['vencimento'])}, referente à moto {cobranca['placa']}, tem saldo de {formatar_moeda(cobranca['saldo'])}, antes dos encargos. Por favor, entre em contato para regularizar.",
            language=None,
        )
        tabela(cobrancas.historico_pagamentos(cobranca["id"]), "pagamentos")
        if cobranca["situacao"] in ("aberta", "atrasada"):
            data = st.date_input("Data do pagamento", hoje_br(), format="DD/MM/YYYY")
            encargos = cobrancas.calcular_encargos_cobranca(cobranca, data)
            st.info(
                f"Multa: {formatar_moeda(encargos['multa'])} • Juros: {formatar_moeda(encargos['juros'])} • Total sugerido: {formatar_moeda(encargos['total'])}"
            )
            with st.form("pagamento_" + cobranca["id"]):
                valor = st.text_input("Principal recebido (R$)", str(cobranca["saldo"]))
                extras = st.text_input(
                    "Multa e juros recebidos (R$)",
                    str(encargos["multa"] + encargos["juros"]),
                )
                forma = st.selectbox(
                    "Forma", ["pix", "dinheiro", "cartao", "transferencia", "outro"]
                )
                observacoes = st.text_area("Observações")
                if st.form_submit_button("Registrar pagamento", type="primary"):
                    cobrancas.registrar_pagamento(
                        cobranca["id"],
                        data,
                        decimal_br(valor, positivo=True),
                        decimal_br(extras),
                        forma,
                        observacoes,
                    )
                    sucesso()
