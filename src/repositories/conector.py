"""RPCs do conector do claude.ai (seção 24 do plano). O usuário de serviço do conector não lê tabela nenhuma: só chama estas funções.

As que gravam descartam o cache de leituras do app (o conector roda no mesmo processo das telas), mesmo quando a gravação falha."""

from src.db import get_client
from src.repositories.consultas import invalida_cache


def cobrancas_abertas(busca: str, limite: int = 20) -> list[dict]:
    return get_client().rpc("rpc_conector_cobrancas_abertas", {"p_busca": busca, "p_limite": limite}).execute().data or []


def veiculos(busca: str, limite: int = 10) -> list[dict]:
    return get_client().rpc("rpc_conector_veiculos", {"p_busca": busca, "p_limite": limite}).execute().data or []


def ultimos_lancamentos(limite: int = 10) -> list[dict]:
    return get_client().rpc("rpc_conector_minhas_pendencias", {"p_limite": limite}).execute().data or []


def _gravar(rpc: str, payload: dict) -> dict:
    return get_client().rpc(rpc, {"payload": payload}).execute().data


@invalida_cache
def registrar_pagamento(payload: dict) -> dict:
    return _gravar("rpc_conector_registrar_pagamento", payload)


@invalida_cache
def registrar_despesa(payload: dict) -> dict:
    return _gravar("rpc_conector_registrar_despesa", payload)


@invalida_cache
def cadastrar_cliente(payload: dict) -> dict:
    return _gravar("rpc_conector_cadastrar_cliente", payload)


@invalida_cache
def cadastrar_veiculo(payload: dict) -> dict:
    return _gravar("rpc_conector_cadastrar_veiculo", payload)


# ---- Histórico dos chats (rascunho que o dono confere; nada entra no financeiro) ----

def entregar_lote_historico(payload: dict) -> dict:
    return _gravar("rpc_conector_entregar_lote_historico", payload)


def resumo_historico(fonte: str | None = None) -> dict:
    return get_client().rpc("rpc_conector_resumo_historico", {"p_fonte": fonte}).execute().data or {"lotes": [], "contagens": []}


def historico_a_conferir(fonte: str | None = None, situacao: str | None = None, limite: int = 30, pagina: int = 1, tipo: str | None = None) -> dict:
    """{"total", "pagina", "por_pagina", "linhas": [...]}."""
    vazio = {"total": 0, "pagina": pagina, "por_pagina": limite, "linhas": []}
    return get_client().rpc("rpc_conector_historico_a_conferir", {"p_fonte": fonte, "p_situacao": situacao, "p_limite": limite,
                                                                   "p_pagina": pagina, "p_tipo": tipo}).execute().data or vazio
