"""Cadastro de clientes (locatários)."""

import streamlit as st

from src.services import clientes, contratos, cobrancas
from src.domain.valores import hoje_br
from src.ui.componentes import (
    cabecalho,
    proteger,
    selecionar,
    tabela,
    campo_data,
    sucesso,
)

cabecalho("Clientes")
with proteger():
    registros = clientes.listar()
    busca = st.text_input("Buscar nome")
    filtro = st.selectbox("Situação", ["Todos", "ativo", "bloqueado", "inativo"])
    tabela(
        [
            c
            for c in registros
            if busca.casefold() in c["nome"].casefold()
            and (filtro == "Todos" or c["status"] == filtro)
        ],
        "clientes",
        ["nome", "cpf", "telefone", "status", "cnh_validade"],
    )
    modo = st.radio("Cadastro", ["Novo cliente", "Editar cliente"], horizontal=True)
    cliente = (
        {}
        if modo == "Novo cliente"
        else selecionar("Cliente", registros, lambda c: c["nome"], "editar_cliente")
    )
    if cliente is not None:
        with st.form("cliente_" + cliente.get("id", "novo")):
            dados = {}
            for campo, titulo in [
                ("nome", "Nome completo"),
                ("cpf", "CPF"),
                ("telefone", "Telefone"),
                ("whatsapp", "WhatsApp"),
                ("email", "E-mail"),
                ("endereco", "Endereço"),
                ("cnh_numero", "Número da CNH"),
                ("cnh_categoria", "Categoria da CNH"),
            ]:
                dados[campo] = st.text_input(titulo, cliente.get(campo) or "")
            validade = campo_data("Validade da CNH", cliente.get("cnh_validade"))
            dados["cnh_validade"] = validade.isoformat() if validade else None
            opcoes = ["ativo", "bloqueado", "inativo"]
            dados["status"] = st.selectbox(
                "Status", opcoes, index=opcoes.index(cliente.get("status", "ativo"))
            )
            dados["observacoes"] = st.text_area(
                "Observações", cliente.get("observacoes") or ""
            )
            if st.form_submit_button("Salvar cliente", type="primary"):
                if cliente:
                    clientes.atualizar(cliente["id"], dados)
                else:
                    clientes.criar(dados)
                sucesso()
        if cliente:
            if (
                cliente.get("cnh_validade")
                and cliente["cnh_validade"] < hoje_br().isoformat()
            ):
                st.warning("A CNH deste cliente está vencida.")
            st.subheader("Histórico de contratos")
            tabela(
                [c for c in contratos.listar() if c["cliente_id"] == cliente["id"]],
                "cliente_contratos",
            )
            st.subheader("Cobranças e pagamentos")
            parcelas = [
                c for c in cobrancas.listar() if c["cliente_id"] == cliente["id"]
            ]
            tabela(parcelas, "cliente_cobrancas")
            parcela = selecionar(
                "Cobrança",
                parcelas,
                lambda c: f"{c['vencimento']} • {c['tipo']}",
                "cliente_parcela",
            )
            if parcela:
                tabela(
                    cobrancas.historico_pagamentos(parcela["id"]), "cliente_pagamentos"
                )
