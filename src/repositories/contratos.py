"""Leitura da tabela contratos e chamadas às RPCs de criação/encerramento.

Criação e encerramento de contrato sempre passam pela RPC (mexem em mais de
uma tabela numa transação só) — não existe inserção direta aqui.
"""

from datetime import date

from src.db import get_client

TABELA = "contratos"


def listar():
    resposta = get_client().table(TABELA).select("*").order("criado_em", desc=True).execute()
    return resposta.data


def obter(contrato_id: str):
    resposta = (
        get_client().table(TABELA).select("*").eq("id", contrato_id).maybe_single().execute()
    )
    return resposta.data if resposta else None


def atualizar(contrato_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", contrato_id).execute()
    return resposta.data[0]


def criar_via_rpc(payload: dict) -> dict:
    resposta = get_client().rpc("rpc_criar_contrato", {"payload": payload}).execute()
    return resposta.data


def encerrar_via_rpc(
    contrato_id: str, data: date, km_final: int, caucao_devolvida: bool
) -> dict:
    resposta = (
        get_client()
        .rpc(
            "rpc_encerrar_contrato",
            {
                "p_contrato_id": contrato_id,
                "p_data": data.isoformat(),
                "p_km_final": km_final,
                "p_caucao_devolvida": caucao_devolvida,
            },
        )
        .execute()
    )
    return resposta.data
