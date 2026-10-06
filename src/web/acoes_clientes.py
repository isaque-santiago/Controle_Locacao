"""Fronteira de escrita das telas web de Clientes."""

from src.services import clientes


def criar_cliente(dados):
    return clientes.criar(dados)


def atualizar_cliente(cliente_id, dados):
    return clientes.atualizar(cliente_id, dados)
