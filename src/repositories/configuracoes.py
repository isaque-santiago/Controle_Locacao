"""Leitura e atualização da linha única de configurações."""

from src.db import get_client

TABELA = "configuracoes"


def obter():
    raise NotImplementedError


def atualizar(dados: dict):
    raise NotImplementedError
