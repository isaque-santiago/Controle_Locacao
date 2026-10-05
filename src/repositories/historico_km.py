"""CRUD da tabela historico_km."""

from src.repositories.consultas import inserir_idempotente, invalida_cache, todos

TABELA = "historico_km"


def listar_por_moto(moto_id: str):
    return todos(TABELA, "data", filtros={"moto_id": moto_id})


@invalida_cache
def criar(dados: dict, chave_operacao=None):
    return inserir_idempotente(TABELA, dados, chave_operacao)
