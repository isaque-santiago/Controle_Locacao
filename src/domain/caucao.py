"""Devolução da caução no encerramento do contrato (regra da operação, seção 14.3 do plano).

Os danos causados pelo cliente são descontados da caução: devolução = caução − danos.
Se os danos passarem da caução, a devolução é zero e o excedente é cobrado do cliente
(cobrança `tipo = 'dano'`). Espelha a regra da RPC `rpc_encerrar_contrato`.
"""

from decimal import ROUND_HALF_UP, Decimal

_ZERO = Decimal("0.00")


def _dinheiro(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def caucao_paga(cobrancas) -> Decimal:
    """Valor efetivamente recebido de caução em um contrato (soma do que foi pago nas
    cobranças `tipo = 'caucao'`). É a base da devolução: caução não recebida não se devolve."""
    return sum(
        (_dinheiro(c.get("valor_pago")) for c in cobrancas if c.get("tipo") == "caucao"),
        _ZERO,
    )


def calcular_devolucao_caucao(caucao_recebida, valor_danos) -> dict:
    """Resultado do encerramento para a caução.

    desconto  = min(danos, caução recebida)      -> abatido da caução
    devolucao = caução recebida − desconto       -> devolvida ao cliente
    excedente = danos − desconto                 -> cobrado do cliente (cobrança de dano)
    """
    caucao = _dinheiro(caucao_recebida)
    danos = _dinheiro(valor_danos)
    if caucao < 0 or danos < 0:
        raise ValueError("Caução e danos não podem ser negativos.")
    desconto = min(danos, caucao)
    return {
        "caucao_paga": caucao,
        "danos": danos,
        "desconto": desconto,
        "devolucao": caucao - desconto,
        "excedente": danos - desconto,
    }
