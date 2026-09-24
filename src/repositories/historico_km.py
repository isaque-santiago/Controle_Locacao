"""CRUD da tabela historico_km."""

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "historico_km"


def listar_por_moto(moto_id: str):
    return todos(TABELA, "data", filtros={"moto_id": moto_id})


@invalida_cache
def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]
