"""Leitura completa das views de alerta."""

from src.repositories.consultas import todos


def listar_manutencao():
    # Esta view não possui id; ordenação composta por moto e item.
    return todos("vw_alertas_manutencao", ("moto_id", "item_id"))


def listar_documentos():
    return todos("vw_alertas_documentos", "vencimento")


def listar_cnh():
    # Esta view não possui id; ordenação por cliente.
    return todos("vw_alertas_cnh", ("cliente_id",))
