"""CRUD da tabela itens_manutencao (catálogo)."""

from src.db import get_client

TABELA = "itens_manutencao"


def listar():
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError


def atualizar(item_id: str, dados: dict):
    raise NotImplementedError
