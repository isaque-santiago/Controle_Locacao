"""Leitura da tabela manutencoes e chamada à RPC de registro.

Registrar manutenção sempre passa pela RPC (grava manutencao + itens + plano
+ histórico de km + status da moto numa transação só).
"""

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "manutencoes"


@invalida_cache
def finalizar(manutencao_id, status, data_saida, km):
    return (
        get_client()
        .rpc(
            "rpc_finalizar_manutencao",
            {
                "payload": {
                    "id": manutencao_id,
                    "status": status,
                    "data": data_saida.isoformat(),
                    "km": km,
                }
            },
        )
        .execute()
        .data
    )


def listar(moto_id: str = None):
    return todos(
        TABELA,
        "data_entrada",
        "*, itens:manutencao_itens(*)",
        {"moto_id": moto_id} if moto_id else None,
    )


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


@invalida_cache
def registrar_via_rpc(payload: dict) -> dict:
    resposta = (
        get_client().rpc("rpc_registrar_manutencao", {"payload": payload}).execute()
    )
    return resposta.data
