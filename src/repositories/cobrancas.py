"""Leitura da tabela cobrancas (via vw_cobrancas, com saldo e situação) e RPCs."""

from src.db import get_client
from src.repositories.consultas import invalida_cache, limpar_cache, todos

TABELA = "cobrancas"
VIEW = "vw_cobrancas"


def listar():
    return todos(VIEW, ordem="vencimento")


def listar_por_contrato(contrato_id: str):
    return todos(VIEW, "vencimento", filtros={"contrato_id": contrato_id})


def obter(cobranca_id: str):
    resposta = (
        get_client()
        .table(VIEW)
        .select("*")
        .eq("id", cobranca_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


@invalida_cache
def atualizar(cobranca_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", cobranca_id).execute()
    return resposta.data[0]


def gerar_pendentes_via_rpc(horizonte_dias: int = 30) -> dict:
    resposta = (
        get_client()
        .rpc("rpc_gerar_cobrancas_pendentes", {"p_horizonte_dias": horizonte_dias})
        .execute()
    )
    # Só descarta o cache se algo foi de fato criado (o caso comum é não gerar nada).
    if (resposta.data or {}).get("cobrancas_geradas"):
        limpar_cache()
    return resposta.data
