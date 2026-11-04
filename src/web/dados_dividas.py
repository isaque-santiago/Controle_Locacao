"""Fronteira de leitura da página web de Dívidas. Os testes das rotas trocam este serviço por dados fictícios."""

from src.services import dividas


def resumo():
    return dividas.resumo()
