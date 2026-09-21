"""CRUD da tabela historico_km."""

from src.db import get_client

TABELA = "historico_km"


def listar_por_moto(moto_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("moto_id", moto_id)
        .order("data", desc=True)
        .execute()
    )
    return resposta.data


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]
