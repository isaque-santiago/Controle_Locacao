"""CRUD (somente inserção e leitura) da tabela pagamentos."""

from src.db import get_client

TABELA = "pagamentos"


def listar_por_cobranca(cobranca_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("cobranca_id", cobranca_id)
        .order("data_pagamento", desc=True)
        .execute()
    )
    return resposta.data


def obter(pagamento_id: str):
    resposta = (
        get_client().table(TABELA).select("*").eq("id", pagamento_id).maybe_single().execute()
    )
    return resposta.data if resposta else None


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]
