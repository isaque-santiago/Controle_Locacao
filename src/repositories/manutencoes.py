"""CRUD da tabela manutencoes."""

from src.db import get_client

TABELA = "manutencoes"


def listar():
    raise NotImplementedError


def obter(manutencao_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError
