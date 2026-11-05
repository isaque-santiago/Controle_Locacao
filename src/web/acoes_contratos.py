"""Fronteira de escrita das telas web de Contratos."""

from src.services import contratos


def criar_contrato_com_vistoria(dados, vistoria, vistorias_vinculadas=None):
    """Cria o contrato e a vistoria de entrega na mesma transação (RPC). Devolve {"contrato_id", ...}.
    Com motos vinculadas, a tela exige a vistoria de entrega de todas."""
    return contratos.criar_com_vistoria(dados, vistoria, vistorias_vinculadas, exigir_todas=True)


def encerrar_contrato_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao_danos, vistorias_vinculadas=None):
    """Encerra o contrato com a vistoria de devolução (RPC); os danos saem da caução e o excedente vira cobrança.
    Com motos vinculadas, a tela exige a vistoria de devolução de todas."""
    return contratos.encerrar_com_vistoria(
        contrato_id, data, vistoria, valor_danos, descricao_danos, vistorias_vinculadas, exigir_todas=True
    )
