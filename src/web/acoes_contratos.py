"""Fronteira de escrita das telas web de Contratos."""

from src.services import contratos


def criar_contrato_com_vistoria(dados, vistoria):
    """Cria o contrato e a vistoria de entrega na mesma transação (RPC). Devolve {"contrato_id", ...}."""
    return contratos.criar_com_vistoria(dados, vistoria)


def encerrar_contrato_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao_danos):
    """Encerra o contrato com a vistoria de devolução (RPC); os danos saem da caução e o excedente vira cobrança."""
    return contratos.encerrar_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao_danos)
