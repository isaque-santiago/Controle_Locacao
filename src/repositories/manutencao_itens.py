"""Leitura da tabela manutencao_itens.

Inserção sempre via rpc_registrar_manutencao (repositories/manutencoes.py) —
não existe inserção direta aqui.
"""

from src.db import get_client

TABELA = "manutencao_itens"


def listar_por_manutencao(manutencao_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("manutencao_id", manutencao_id)
        .execute()
    )
    return resposta.data
