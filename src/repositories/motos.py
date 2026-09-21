"""CRUD da tabela motos."""

from src.db import get_client

TABELA = "motos"


def listar():
    raise NotImplementedError


def obter(moto_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError


def atualizar(moto_id: str, dados: dict):
    raise NotImplementedError
