"""Fronteira de escrita das telas web de Contratos."""

from src.services import contratos


def criar_contrato_com_vistoria(dados, vistoria):
    """Cria o contrato e a vistoria de entrega na mesma transação (RPC). Devolve {"contrato_id", ...}."""
    return contratos.criar_com_vistoria(dados, vistoria)
