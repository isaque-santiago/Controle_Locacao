"""Alertas, registro e catálogo de manutenção."""

import streamlit as st

from src.services import manutencao, motos, alertas
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import cabecalho, proteger, selecionar, tabela, sucesso

cabecalho("Manutenção")
with proteger():
    avisos, registro, catalogo = st.tabs(
        ["Alertas e histórico", "Registrar manutenção", "Catálogo"]
    )
    frota = motos.listar()
    itens = manutencao.listar_catalogo()
    with avisos:
        tabela(alertas.listar_manutencao(), "alertas_man")
        historico = manutencao.listar_manutencoes()
        tabela(historico, "historico_man")
        aberta = selecionar(
            "Manutenção aberta",
            [m for m in historico if m["status"] == "aberta"],
            lambda m: f"{m['data_entrada']} • {m['descricao']}",
            "man_aberta",
        )
        if aberta:
            with st.form("concluir_" + aberta["id"]):
                data_saida = st.date_input(
                    "Data de conclusão", hoje_br(), format="DD/MM/YYYY"
                )
                km_atual = next(
                    m["km_atual"] for m in frota if m["id"] == aberta["moto_id"]
                )
                km = st.number_input(
                    "Km na conclusão",
                    min_value=max(km_atual, aberta["km"]),
                    value=max(km_atual, aberta["km"]),
                )
                acao = st.selectbox("Ação", ["concluida", "cancelada"])
                if st.form_submit_button("Atualizar manutenção"):
                    manutencao.finalizar(aberta["id"], acao, data_saida, km)
                    sucesso()
    with registro:
        moto = selecionar(
            "Moto",
            [m for m in frota if m["status"] != "inativa"],
            lambda m: m["placa"],
            "man_moto",
        )
        escolhidos = st.multiselect(
            "Itens substituídos ou revisados",
            [i["id"] for i in itens if i["ativo"]],
            format_func=lambda id: next(i["nome"] for i in itens if i["id"] == id),
        )
        if moto:
            with st.form("man_nova_" + moto["id"]):
                tipo = st.selectbox("Tipo", ["preventiva", "corretiva"])
                status = st.selectbox("Status", ["concluida", "aberta"])
                entrada = st.date_input(
                    "Data de entrada", hoje_br(), format="DD/MM/YYYY"
                )
                km = st.number_input(
                    "Km", min_value=moto["km_atual"], value=moto["km_atual"]
                )
                descricao = st.text_input("Descrição do serviço")
                oficina = st.text_input("Oficina")
                mao_obra = st.text_input("Mão de obra (R$)", "0")
                cobrar = st.checkbox("Cobrar do cliente com contrato ativo")
                valores = []
                for id in escolhidos:
                    item = next(i for i in itens if i["id"] == id)
                    st.markdown(f"**{item['nome']}**")
                    quantidade = st.text_input("Quantidade", "1", key=id + "_qtd")
                    valor = st.text_input("Valor unitário (R$)", "0", key=id + "_valor")
                    valores.append((item, quantidade, valor))
                outro = st.text_input("Outra peça ou serviço (opcional)")
                outro_valor = st.text_input("Custo da outra peça (R$)", "0")
                if st.form_submit_button("Registrar manutenção", type="primary"):
                    if not descricao.strip():
                        raise ValueError("Informe a descrição do serviço.")
                    lista = [
                        {
                            "item_id": i["id"],
                            "descricao": i["nome"],
                            "quantidade": decimal_br(q, positivo=True),
                            "valor_unitario": decimal_br(v),
                        }
                        for i, q, v in valores
                    ]
                    if outro.strip():
                        lista.append(
                            {
                                "descricao": outro,
                                "quantidade": 1,
                                "valor_unitario": decimal_br(outro_valor),
                            }
                        )
                    manutencao.registrar_manutencao(
                        moto["id"],
                        tipo,
                        entrada,
                        km,
                        descricao,
                        status=status,
                        data_saida=entrada if status == "concluida" else None,
                        oficina=oficina,
                        custo_mao_obra=decimal_br(mao_obra),
                        cobrar_do_cliente=cobrar,
                        itens=lista,
                    )
                    sucesso()
    with catalogo:
        tabela(itens, "catalogo")
        modo = st.radio("Catálogo", ["Novo item", "Editar item"])
        item = (
            {}
            if modo == "Novo item"
            else selecionar("Item", itens, lambda i: i["nome"], "catalogo_item")
        )
        if item is not None:
            with st.form("catalogo_" + item.get("id", "novo")):
                nome = st.text_input("Nome", item.get("nome", ""))
                km = st.number_input(
                    "Intervalo km (0 sem limite)",
                    min_value=0,
                    value=item.get("intervalo_km") or 0,
                )
                dias = st.number_input(
                    "Intervalo dias (0 sem limite)",
                    min_value=0,
                    value=item.get("intervalo_dias") or 0,
                )
                ativo = st.checkbox("Ativo", item.get("ativo", True))
                if st.form_submit_button("Salvar item"):
                    if not nome.strip() or not (km or dias):
                        raise ValueError("Informe o nome e pelo menos um intervalo.")
                    dados = {
                        "nome": nome,
                        "intervalo_km": km or None,
                        "intervalo_dias": dias or None,
                        "ativo": ativo,
                    }
                    if item:
                        manutencao.atualizar_item_catalogo(item["id"], dados)
                    else:
                        manutencao.criar_item_catalogo(dados)
                    sucesso()
