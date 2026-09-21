"""CRUD da tabela moto_plano_manutencao."""

from src.db import get_client

TABELA = "moto_plano_manutencao"


def listar_por_moto(moto_id: str):
    raise NotImplementedError


def atualizar(plano_id: str, dados: dict):
    raise NotImplementedError
