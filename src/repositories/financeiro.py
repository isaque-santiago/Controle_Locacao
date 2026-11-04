"""Leituras do dashboard financeiro: totais mensais (RPC) e saldo das dívidas (view)."""

from datetime import date

from src.db import get_client
from src.repositories.consultas import todos


def resumo_mensal(mes: date, quantidade: int = 6) -> list:
    """`quantidade` meses terminando em `mes`, do mais antigo ao mais recente (RPC `rpc_resumo_financeiro`)."""
    resposta = (
        get_client()
        .rpc("rpc_resumo_financeiro", {"p_mes": mes.isoformat(), "p_meses": quantidade})
        .execute()
        .data
    )
    return resposta["meses"]


def saldos_dividas() -> list:
    return todos("vw_saldo_dividas", ordem=("divida_id",))
