"""CRUD da tabela cobrancas."""

from src.db import get_client

TABELA = "cobrancas"


def listar():
    raise NotImplementedError


def obter(cobranca_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError


def atualizar(cobranca_id: str, dados: dict):
    raise NotImplementedError
