"""CRUD (somente inserção e leitura) da tabela pagamentos."""

from src.db import get_client
from src.repositories.consultas import todos

TABELA = "pagamentos"


def listar_por_cobranca(cobranca_id: str):
    return todos(TABELA, "data_pagamento", filtros={"cobranca_id": cobranca_id})


def obter(pagamento_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("id", pagamento_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]
