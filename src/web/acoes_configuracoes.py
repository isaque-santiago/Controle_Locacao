"""Fronteira de escrita da página Configurações."""

from src.services import arquivos_orfaos, configuracoes


def atualizar(dados):
    """Grava os parâmetros (o serviço valida de novo) e devolve a linha salva."""
    return configuracoes.atualizar(dados)


def apagar_arquivos_orfaos():
    """Apaga os arquivos órfãos do portal (a lista é recalculada no banco, não vem da tela). Devolve {apagados, tamanho, falhas}."""
    return arquivos_orfaos.apagar()
