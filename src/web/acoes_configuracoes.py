"""Fronteira de escrita da página Configurações."""

from src.services import configuracoes


def atualizar(dados):
    """Grava os parâmetros (o serviço valida de novo) e devolve a linha salva."""
    return configuracoes.atualizar(dados)
