"""CRUD da tabela motos."""

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "motos"


def listar():
    return todos(TABELA, ordem="placa")


def obter(moto_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("id", moto_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


@invalida_cache
def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


@invalida_cache
def atualizar(moto_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", moto_id).execute()
    return resposta.data[0]


@invalida_cache
def arquivar_via_rpc(moto_id: str, motivo: str, vendida_em: str | None) -> dict:
    parametros = {"p_moto": moto_id, "p_motivo": motivo, "p_vendida_em": vendida_em}
    return get_client().rpc("rpc_arquivar_moto", parametros).execute().data


@invalida_cache
def desarquivar_via_rpc(moto_id: str) -> dict:
    return get_client().rpc("rpc_desarquivar_moto", {"p_moto": moto_id}).execute().data
