"""CRUD da tabela documentos_moto."""

from src.db import get_client

TABELA = "documentos_moto"


def listar_por_moto(moto_id: str):
    raise NotImplementedError


def criar(dados: dict):
    raise NotImplementedError


def atualizar(documento_id: str, dados: dict):
    raise NotImplementedError
