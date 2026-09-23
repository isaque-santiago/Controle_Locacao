"""Leitura do plano de manutenção por moto (join com itens_manutencao) e RPCs."""

from src.db import get_client
from src.repositories.consultas import invalida_cache

TABELA = "moto_plano_manutencao"


def listar_por_moto(moto_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, item:itens_manutencao(*)")
        .eq("moto_id", moto_id)
        .execute()
    )
    return resposta.data


def obter(plano_id: str):
    resposta = (
        get_client().table(TABELA).select("*").eq("id", plano_id).maybe_single().execute()
    )
    return resposta.data if resposta else None


@invalida_cache
def atualizar(plano_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", plano_id).execute()
    return resposta.data[0]


@invalida_cache
def aplicar_plano_padrao_via_rpc(moto_id: str) -> dict:
    resposta = (
        get_client().rpc("rpc_aplicar_plano_padrao", {"p_moto_id": moto_id}).execute()
    )
    return resposta.data
