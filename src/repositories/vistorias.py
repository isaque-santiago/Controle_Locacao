"""CRUD da tabela vistorias."""

from src.db import get_client

TABELA = "vistorias"


def listar_por_contrato(contrato_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError
