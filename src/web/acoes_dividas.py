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


def atualizar_divida(divida_id, dados):
    return dividas.atualizar_divida(divida_id, dados)


def confirmar_saldo(divida_id, saldo, data):
    return dividas.confirmar_saldo(divida_id, saldo, data)


def apagar_divida(divida_id):
    return dividas.apagar_divida(divida_id)


def atualizar_parcela(vencimento_id, vencimento, valor):
    return dividas.atualizar_parcela(vencimento_id, vencimento, valor)


def atualizar_pagamento(pagamento_id, data, valor, conta_id, observacoes, data_estimada):
    return dividas.atualizar_pagamento(pagamento_id, data, valor, conta_id, observacoes, data_estimada)
