"""Leitura do rascunho do histórico dos chats, só para o dono (a RLS barra os demais). Quem grava é o conector, pelas RPCs."""

from src.db import get_client
from src.repositories.consultas import todos


def conferencia(fonte: str | None = None, situacao: str | None = None) -> dict:
    """{"total", "linhas": [...]} com todos os registros (trecho, lote, motivo da comparação). Só o dono."""
    return get_client().rpc("rpc_historico_conferencia", {"p_fonte": fonte, "p_situacao": situacao}).execute().data or {"total": 0, "linhas": []}


def lotes() -> list[dict]:
    return todos("historico_chat_lotes", "periodo_inicio", usar_cache=False)
