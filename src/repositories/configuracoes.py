"""Leitura e atualização da linha única de configurações."""

from src.db import get_client
from src.repositories.consultas import invalida_cache

TABELA = "configuracoes"


def obter():
    resposta = get_client().table(TABELA).select("*").eq("id", 1).single().execute()
    return resposta.data


@invalida_cache
def atualizar(dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", 1).execute()
    return resposta.data[0]
