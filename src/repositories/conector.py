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
