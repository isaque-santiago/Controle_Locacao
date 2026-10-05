"""Efeitos do encerramento de um contrato, para o dono ver o que será afetado antes de confirmar.

Espelha a regra da RPC `rpc_encerrar_contrato_com_vistoria`: ao encerrar, as cobranças ainda
abertas com vencimento depois da data de encerramento e sem nenhum pagamento são canceladas.
Cobranças vencidas até a data, ou com pagamento parcial, continuam em aberto.
"""

from datetime import date
from decimal import Decimal

_SITUACOES_EM_ABERTO = ("aberta", "atrasada")


def _data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def cobrancas_a_cancelar(cobrancas, data_encerramento) -> list:
    """Cobranças que o encerramento cancela, em ordem de vencimento."""
    limite = _data(data_encerramento)
    afetadas = [
        c
        for c in cobrancas
        if c.get("situacao") in _SITUACOES_EM_ABERTO
        and _data(c["vencimento"]) > limite
        and Decimal(str(c.get("valor_pago") or 0)) == 0
    ]
    return sorted(afetadas, key=lambda c: _data(c["vencimento"]))
