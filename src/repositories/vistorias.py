"""Leitura da tabela vistorias e chamada à RPC de registro.

Registrar vistoria sempre passa pela RPC (grava vistoria + histórico de km
numa transação só) — não existe inserção direta aqui.
"""

from src.db import get_client

TABELA = "vistorias"


def listar_por_contrato(contrato_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, fotos:vistoria_fotos(*)")
        .eq("contrato_id", contrato_id)
        .order("data")
        .execute()
    )
    return resposta.data


def obter(vistoria_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, fotos:vistoria_fotos(*)")
        .eq("id", vistoria_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


def obter_por_contrato_e_tipo(contrato_id: str, tipo: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, fotos:vistoria_fotos(*)")
        .eq("contrato_id", contrato_id)
        .eq("tipo", tipo)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


def registrar_via_rpc(payload: dict) -> dict:
    resposta = get_client().rpc("rpc_registrar_vistoria", {"payload": payload}).execute()
    return resposta.data
