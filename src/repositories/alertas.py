"""Leitura completa das views de alerta."""

from src.repositories.consultas import todos


def listar_manutencao():
    # Esta view não possui id; ordenação composta por moto e item.
    from src.db import get_client

    registros = []
    while True:
        pagina = (
            get_client()
            .table("vw_alertas_manutencao")
            .select("*")
            .order("moto_id")
            .order("item_id")
            .range(len(registros), len(registros) + 499)
            .execute()
            .data
        )
        if not pagina:
            return registros
        registros.extend(pagina)


def listar_documentos():
    return todos("vw_alertas_documentos", "vencimento")


def listar_cnh():
    from src.db import get_client

    registros = []
    while True:
        pagina = (
            get_client()
            .table("vw_alertas_cnh")
            .select("*")
            .order("cliente_id")
            .range(len(registros), len(registros) + 499)
            .execute()
            .data
        )
        if not pagina:
            return registros
        registros.extend(pagina)
