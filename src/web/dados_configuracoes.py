"""Fronteira de leitura da página web de Configurações. Os testes das rotas trocam estes serviços por dados fictícios."""

from src.domain.configuracoes import exemplo_encargos
from src.services import configuracoes


def obter():
    return configuracoes.obter()


def exemplo(config):
    """Cálculo de encargos com os valores hoje salvos (o formulário só grava ao salvar)."""
    return exemplo_encargos(config["multa_atraso_valor"], config["encargo_diario_valor"])


def gerar_backup():
    """ZIP com um CSV de cada tabela acessível, manifesto e LEIA-ME. Contém dados pessoais."""
    return configuracoes.backup()
