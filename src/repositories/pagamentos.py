"""CRUD da tabela pagamentos."""

from src.db import get_client

TABELA = "pagamentos"


def listar():
    raise NotImplementedError


def obter(pagamento_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError
