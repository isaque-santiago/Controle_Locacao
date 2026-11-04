"""Fronteira de escrita da página Dívidas."""

from src.services import dividas


def pagar_parcela(vencimento_id, data, valor, conta_id, observacoes):
    return dividas.pagar_parcela(vencimento_id, data, valor, conta_id, observacoes)


def criar_compra_parcelada(dados):
    return dividas.criar_compra_parcelada(**dados)


def criar_divida(dados):
    return dividas.criar_divida(**dados)


def pagar_divida(divida_id, data, valor, conta_id, observacoes):
    return dividas.pagar_divida(divida_id, data, valor, conta_id, observacoes)
