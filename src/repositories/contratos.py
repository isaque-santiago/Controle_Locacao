"""CRUD da tabela contratos."""

from src.db import get_client

TABELA = "contratos"


def listar():
    raise NotImplementedError


def obter(contrato_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError


def atualizar(contrato_id: str, dados: dict):
    raise NotImplementedError
