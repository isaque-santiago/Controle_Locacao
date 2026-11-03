"""Compra a prazo como dívida (ex.: Celta, R$ 14.000 = entrada de R$ 5.000 + 9 parcelas mensais de R$ 1.000).

Funções puras, no mesmo critério da RPC `rpc_criar_compra_parcelada`: total = entrada + parcelas x valor da
parcela, e os vencimentos mantêm o dia da primeira parcela (em mês curto vale o último dia do mês).
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta

_CENTAVOS = Decimal("0.01")


def validar_compra_parcelada(
    valor_total: Decimal,
    valor_entrada: Decimal,
    numero_parcelas: int,
    valor_parcela: Decimal,
    parcelas_pagas: int = 0,
) -> None:
    """Levanta ValueError se os números não fecham."""
    if numero_parcelas <= 0:
        raise ValueError("Informe o número de parcelas.")
    if valor_parcela <= 0:
        raise ValueError("O valor da parcela deve ser positivo.")
    if valor_entrada < 0:
        raise ValueError("A entrada não pode ser negativa.")
    if not 0 <= parcelas_pagas <= numero_parcelas:
        raise ValueError("As parcelas pagas devem estar entre 0 e o número de parcelas.")
    esperado = valor_entrada + numero_parcelas * valor_parcela
    if valor_total != esperado:
        raise ValueError(f"O total (R$ {valor_total}) deve ser igual à entrada mais as parcelas (R$ {esperado}).")


def calendario_parcelas(primeira_parcela: date, numero_parcelas: int) -> list:
    """Vencimentos mensais: a n-ésima parcela vence `n-1` meses depois da primeira, no mesmo dia."""
    if numero_parcelas <= 0:
        raise ValueError("Informe o número de parcelas.")
    return [primeira_parcela + relativedelta(months=i) for i in range(numero_parcelas)]


def saldo_compra(
    valor_total: Decimal, valor_entrada: Decimal, valor_parcela: Decimal, parcelas_pagas: int
) -> Decimal:
    """O que falta pagar depois da entrada e das parcelas já pagas."""
    return (valor_total - valor_entrada - valor_parcela * parcelas_pagas).quantize(_CENTAVOS)


def situacao_parcela(
    vencimento: Optional[date], valor: Decimal, valor_pago: Decimal, hoje: date
) -> str:
    """'paga', 'sem_data', 'atrasada' ou 'a_vencer' (mesma regra da view `vw_parcelas_divida`)."""
    if valor_pago >= valor:
        return "paga"
    if vencimento is None:
        return "sem_data"
    return "atrasada" if vencimento < hoje else "a_vencer"


def dias_atraso_parcela(vencimento: Optional[date], valor: Decimal, valor_pago: Decimal, hoje: date) -> int:
    if vencimento is None or valor_pago >= valor or vencimento >= hoje:
        return 0
    return (hoje - vencimento).days
