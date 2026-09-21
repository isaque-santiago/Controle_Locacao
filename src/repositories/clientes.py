"""CRUD da tabela clientes."""

from src.db import get_client

TABELA = "clientes"


def listar():
    resposta = get_client().table(TABELA).select("*").order("nome").execute()
    return resposta.data


def obter(cliente_id: str):
    resposta = (
        get_client().table(TABELA).select("*").eq("id", cliente_id).maybe_single().execute()
    )
    return resposta.data if resposta else None


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


def atualizar(cliente_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", cliente_id).execute()
    return resposta.data[0]
