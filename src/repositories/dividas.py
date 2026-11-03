"""Compra a prazo como dívida: criação, pagamento de parcela e leitura (sempre por RPC ou view).

Criar a dívida e pagar uma parcela mexem em mais de uma tabela, então passam por RPC (transação única).
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.db import get_client
from src.repositories.consultas import invalida_cache


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
