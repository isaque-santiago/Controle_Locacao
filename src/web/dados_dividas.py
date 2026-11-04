"""Fronteira de leitura da página web de Dívidas. Os testes das rotas trocam este serviço por dados fictícios."""

from src.services import dividas


def resumo():
    return dividas.resumo()


def ficha(divida_id):
    return dividas.ficha(divida_id)


def parcela(vencimento_id):
    return dividas.parcela(vencimento_id)


def contas():
    return dividas.contas_ativas()


def motos():
    return dividas.motos_para_selecao()
