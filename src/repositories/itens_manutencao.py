"""CRUD da tabela itens_manutencao (catálogo)."""

from src.db import get_client

TABELA = "itens_manutencao"


def listar(somente_ativos: bool = False):
    consulta = get_client().table(TABELA).select("*").order("nome")
    if somente_ativos:
        consulta = consulta.eq("ativo", True)
    return consulta.execute().data


def obter(item_id: str):
    resposta = get_client().table(TABELA).select("*").eq("id", item_id).maybe_single().execute()
    return resposta.data if resposta else None


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


def atualizar(item_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", item_id).execute()
    return resposta.data[0]
