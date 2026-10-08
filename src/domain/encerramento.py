"""Efeitos do encerramento de um contrato, para o dono ver o que será afetado antes de confirmar.

Espelha a regra da RPC `rpc_encerrar_contrato_com_vistoria`: ao encerrar, as cobranças ainda
abertas com vencimento depois da data de encerramento e sem nenhum pagamento são canceladas.
Cobranças vencidas até a data, ou com pagamento parcial, continuam em aberto.
"""

from datetime import date
from decimal import Decimal

from src.domain.caucao import calcular_devolucao_caucao, caucao_paga

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


def resumo_encerramento(cobrancas, data_encerramento, valor_danos) -> dict:
    """O que o encerramento faz: caução recebida, devolução/desconto/excedente e cobranças canceladas.

    `data_encerramento` None (campo inválido ou vazio) não cancela nada; `valor_danos` None conta como zero."""
    recebida = caucao_paga(cobrancas)
    devolucao = calcular_devolucao_caucao(recebida, valor_danos or 0)
    afetadas = cobrancas_a_cancelar(cobrancas, data_encerramento) if data_encerramento else []
    return {"caucao_recebida": recebida, "devolucao": devolucao, "afetadas": afetadas}
