"""Fronteira de escrita da página Dívidas."""

from src.services import dividas


def pagar_parcela(vencimento_id, data, valor, conta_id, observacoes):
    return dividas.pagar_parcela(vencimento_id, data, valor, conta_id, observacoes)
