"""CRUD (somente inserção e leitura) da tabela pagamentos."""

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "pagamentos"
_TAMANHO_PAGINA = 500
_TAMANHO_LOTE_IDS = 100


def listar_por_cobranca(cobranca_id: str):
    return todos(TABELA, "data_pagamento", filtros={"cobranca_id": cobranca_id})


def listar_por_cobrancas(cobranca_ids: list[str]):
    """Lista pagamentos de várias cobranças sem fazer uma consulta por cobrança."""
    ids = list(dict.fromkeys(cobranca_ids))
    registros = []
    for posicao in range(0, len(ids), _TAMANHO_LOTE_IDS):
        lote = ids[posicao : posicao + _TAMANHO_LOTE_IDS]
        inicio = 0
        while True:
            pagina = (
                get_client()
                .table(TABELA)
                .select("*")
                .in_("cobranca_id", lote)
                .order("data_pagamento")
                .order("id")
                .range(inicio, inicio + _TAMANHO_PAGINA - 1)
                .execute()
                .data
            )
            registros.extend(pagina)
            if len(pagina) < _TAMANHO_PAGINA:
                break
            inicio += len(pagina)
    return registros


def obter(pagamento_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("id", pagamento_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


@invalida_cache
def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]
