"""CRUD da tabela clientes."""

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "clientes"


def listar():
    return todos(TABELA, ordem="nome")


def obter(cliente_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("id", cliente_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


@invalida_cache
def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


@invalida_cache
def atualizar(cliente_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", cliente_id).execute()
    return resposta.data[0]
