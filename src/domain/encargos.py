"""Cálculo de multa e juros por atraso."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_DIAS_MES = Decimal("30")
_CEM = Decimal("100")


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_encargos(
    saldo: Decimal,
    vencimento: date,
    data_referencia: date,
    multa_percentual: Decimal,
    juros_mensal_percentual: Decimal,
    carencia_dias: int = 0,
) -> dict:
    """Multa única + juros simples pro rata sobre o saldo em aberto, após a carência.

    dias = max(data_referencia - vencimento - carencia, 0)
    multa = saldo * multa% se dias > 0 senão 0
    juros = saldo * (juros_mensal% / 30) * dias
    """
    dias_atraso = max((data_referencia - vencimento).days - carencia_dias, 0)

    if dias_atraso <= 0:
        multa = Decimal("0.00")
        juros = Decimal("0.00")
    else:
        multa = _arredondar(saldo * multa_percentual / _CEM)
        juros = _arredondar(saldo * juros_mensal_percentual / _CEM / _DIAS_MES * dias_atraso)

    return {
        "dias_atraso": dias_atraso,
        "multa": multa,
        "juros": juros,
        "total": saldo + multa + juros,
    }
