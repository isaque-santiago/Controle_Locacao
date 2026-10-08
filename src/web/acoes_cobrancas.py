"""Fronteira de escrita da página Cobranças."""

from src.services import cobrancas


def registrar_pagamento(cobranca_id, data, principal, extras, forma, observacoes, chave_operacao):
    """Registra o pagamento; repetir a mesma `chave_operacao` devolve o já gravado em vez de lançar outro."""
    return cobrancas.registrar_pagamento(
        cobranca_id, data, principal, extras, forma, observacoes, chave_operacao=chave_operacao
    )
