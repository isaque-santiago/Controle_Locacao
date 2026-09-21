"""Formulário compartilhado entre contratos e vistorias."""

import streamlit as st
from src.services import vistorias


def campos(chave, km):
    leitura = st.number_input(
        "Quilometragem da vistoria", min_value=km, value=km, step=1, key=chave + "_km"
    )
    combustivel = st.selectbox(
        "Combustível", ["vazio", "1/4", "1/2", "3/4", "cheio"], key=chave + "_comb"
    )
    checklist = {}
    for item in vistorias.checklist_padrao():
        checklist[item] = st.selectbox(
            item.replace("_", " ").capitalize(),
            ["ok", "avaria", "ausente", "nao_aplicavel"],
            key=chave + item,
        )
    adicionais = st.text_area(
        "Itens adicionais (um por linha: nome=estado)", key=chave + "_extras"
    )
    avarias = st.text_area("Descrição das avarias", key=chave + "_avarias")
    return {
        "km": leitura,
        "nivel_combustivel": combustivel,
        "checklist": checklist,
        "avarias": avarias,
        "adicionais": adicionais,
    }


def preparar(dados):
    dados = dict(dados)
    dados["checklist"] = dict(dados["checklist"])
    for linha in dados.pop("adicionais", "").splitlines():
        if not linha.strip():
            continue
        nome, separador, estado = linha.partition("=")
        if (
            not separador
            or not nome.strip()
            or estado.strip() not in ("ok", "avaria", "ausente", "nao_aplicavel")
        ):
            raise ValueError(
                "Use nome=estado nos itens adicionais, com estado ok, avaria, ausente ou nao_aplicavel."
            )
        dados["checklist"][nome.strip()] = estado.strip()
    return dados
