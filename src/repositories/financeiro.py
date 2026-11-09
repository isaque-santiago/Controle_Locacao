"""Leituras do dashboard financeiro: totais e detalhes do mês (RPC), saldo das dívidas e resultado por veículo (views)."""

from datetime import date

from src.db import get_client
from src.repositories import dividas as repositorio_dividas
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


def detalhe_mensal(mes: date) -> dict:
    """Entradas por conta, despesas por categoria, a repassar e receita da semana (RPC `rpc_detalhe_financeiro`)."""
    return get_client().rpc("rpc_detalhe_financeiro", {"p_mes": mes.isoformat()}).execute().data


def resultado_por_veiculo() -> list:
    return todos("vw_resultado_moto", ordem=("moto_id",))


def parcelas_de_divida() -> list:
    """Parcelas de todas as dívidas, com situação (view `vw_parcelas_divida`)."""
    return repositorio_dividas.listar_todas_parcelas()
