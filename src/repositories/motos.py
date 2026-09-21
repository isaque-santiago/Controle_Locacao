"""CRUD da tabela motos."""

from src.db import get_client

TABELA = "motos"


def listar():
    resposta = get_client().table(TABELA).select("*").order("placa").execute()
    return resposta.data


def obter(moto_id: str):
    resposta = get_client().table(TABELA).select("*").eq("id", moto_id).maybe_single().execute()
    return resposta.data if resposta else None


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


def atualizar(moto_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", moto_id).execute()
    return resposta.data[0]
