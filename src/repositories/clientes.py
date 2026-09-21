"""CRUD da tabela clientes."""

from src.db import get_client

TABELA = "clientes"


def listar():
    raise NotImplementedError


def obter(cliente_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError


def atualizar(cliente_id: str, dados: dict):
    raise NotImplementedError
