"""Fronteira de leitura da busca global: reúne os serviços e a regra de src/domain/busca_global."""

from src.domain import busca_global
from src.services import clientes, contratos, motos


def buscar(termo: str) -> dict:
    termo = busca_global.normalizar_termo(termo)
    if len(termo) < busca_global.MINIMO_CARACTERES:
        return busca_global.buscar(termo, [], [], [])
    return busca_global.buscar(termo, motos.listar(), clientes.listar(), contratos.listar())
