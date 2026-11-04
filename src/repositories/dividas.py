"""Compra a prazo como dívida: criação, pagamento de parcela e leitura (sempre por RPC ou view).

Criar a dívida e pagar uma parcela mexem em mais de uma tabela, então passam por RPC (transação única).
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos


@invalida_cache
def criar_compra_parcelada(payload: dict) -> dict:
    return get_client().rpc("rpc_criar_compra_parcelada", {"payload": payload}).execute().data


@invalida_cache
def pagar_parcela(
    vencimento_id: str,
    data: date,
    valor: Optional[Decimal],
    conta_id: Optional[str],
    observacoes: Optional[str],
) -> dict:
    return (
        get_client()
        .rpc(
            "rpc_pagar_parcela_divida",
            {
                "p_vencimento_id": vencimento_id,
                "p_data": data.isoformat(),
                "p_valor": None if valor is None else str(valor),
                "p_conta_id": conta_id,
                "p_observacoes": observacoes,
            },
        )
        .execute()
        .data
    )


def listar_parcelas(divida_id: str) -> list:
    """Parcelas da dívida (view `vw_parcelas_divida`), em ordem de número."""
    linhas = get_client().table("vw_parcelas_divida").select("*").eq("divida_id", divida_id).execute().data
    return sorted(linhas, key=lambda p: (p["numero"] is None, p["numero"] or 0))


def listar_saldos() -> list:
    """Saldo de cada dívida (view `vw_saldo_dividas`)."""
    return todos("vw_saldo_dividas", ordem=("divida_id",))


def listar_todas_parcelas() -> list:
    """Parcelas de todas as dívidas (view `vw_parcelas_divida`)."""
    return todos("vw_parcelas_divida", ordem=("vencimento_id",))


def obter(divida_id: str):
    resposta = get_client().table("dividas").select("*").eq("id", divida_id).maybe_single().execute()
    return resposta.data if resposta else None


def listar_pagamentos(divida_id: str) -> list:
    """Pagamentos da dívida, o mais recente primeiro."""
    linhas = todos("pagamentos_divida", ordem="data", filtros={"divida_id": divida_id})
    return sorted(linhas, key=lambda p: (p["data"], p["criado_em"]), reverse=True)


def obter_parcela(vencimento_id: str):
    """Uma parcela com valor pago, saldo e situação (view), ou None."""
    achadas = todos("vw_parcelas_divida", ordem=("vencimento_id",), filtros={"vencimento_id": vencimento_id})
    return achadas[0] if achadas else None


@invalida_cache
def criar_divida(dados: dict) -> dict:
    """Insere uma dívida (uma tabela só, sem RPC)."""
    return get_client().table("dividas").insert(dados).execute().data[0]


@invalida_cache
def registrar_pagamento(dados: dict) -> dict:
    """Insere um pagamento direto da dívida, sem parcela (uma tabela só, sem RPC)."""
    return get_client().table("pagamentos_divida").insert(dados).execute().data[0]
