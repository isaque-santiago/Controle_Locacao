"""Leitura da tabela manutencoes e chamada à RPC de registro.

Registrar manutenção sempre passa pela RPC (grava manutencao + itens + plano
+ histórico de km + status da moto numa transação só).
"""

from src.db import get_client

TABELA = "manutencoes"


def listar(moto_id: str = None):
    consulta = (
        get_client()
        .table(TABELA)
        .select("*, itens:manutencao_itens(*)")
        .order("data_entrada", desc=True)
    )
    if moto_id:
        consulta = consulta.eq("moto_id", moto_id)
    return consulta.execute().data


def obter(manutencao_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, itens:manutencao_itens(*)")
        .eq("id", manutencao_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


def registrar_via_rpc(payload: dict) -> dict:
    resposta = get_client().rpc("rpc_registrar_manutencao", {"payload": payload}).execute()
    return resposta.data
