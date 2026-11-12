"""Fronteira de escrita da página Cobranças."""

from src.services import cobrancas


def registrar_pagamento(cobranca_id, data, principal, extras, forma, observacoes, chave_operacao):
    """Registra o pagamento; repetir a mesma `chave_operacao` devolve o já gravado em vez de lançar outro."""
    return cobrancas.registrar_pagamento(
        cobranca_id, data, principal, extras, forma, observacoes, chave_operacao=chave_operacao
    )


def cancelar_cobranca(cobranca_id, motivo):
    """Cancela a cobrança em aberto e sem pagamento; o motivo fica guardado com ela."""
    return cobrancas.cancelar_cobranca(cobranca_id, motivo)
