"""CRUD da tabela manutencao_itens."""

from src.db import get_client

TABELA = "manutencao_itens"


def listar_por_manutencao(manutencao_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError
