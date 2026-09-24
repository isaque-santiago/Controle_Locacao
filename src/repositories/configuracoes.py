"""Leitura e atualização da linha única de configurações."""

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "configuracoes"


def obter():
    # Linha única, lida pelo cache das listas (a escrita abaixo o invalida).
    return todos(TABELA, filtros={"id": 1})[0]


@invalida_cache
def atualizar(dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", 1).execute()
    return resposta.data[0]
