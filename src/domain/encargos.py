"""Cálculo do encargo fixo por atraso (regra da operação, seção 14.1 do plano).

R$ 15,00 fixos já no dia do vencimento + R$ 7,00 fixos por dia a partir do dia seguinte.
Sem carência. Só incide sobre cobranças de locação com saldo em aberto.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

TIPO_COM_ENCARGOS = "locacao"
_ZERO = Decimal("0.00")


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_encargos(
    tipo: str,
    saldo: Decimal,
    vencimento: date,
    data_referencia: date,
    multa_valor: Decimal,
    adicional_diario_valor: Decimal,
) -> dict:
    """Encargos de uma cobrança na `data_referencia`.

    dias_atraso = max(data_referencia - vencimento, 0)
    se tipo != 'locacao', saldo <= 0 ou data_referencia < vencimento: encargos = 0
    senão: multa = multa_valor; adicional_diario = adicional_diario_valor * dias_atraso

    O encargo é fixo: não depende do saldo (pagamento parcial não o reduz).
    """
    dias_atraso = max((data_referencia - vencimento).days, 0)

    if tipo != TIPO_COM_ENCARGOS or saldo <= 0 or data_referencia < vencimento:
        multa = _ZERO
        adicional = _ZERO
    else:
        multa = _arredondar(multa_valor)
        adicional = _arredondar(adicional_diario_valor * dias_atraso)

    encargos = multa + adicional
    return {
        "dias_atraso": dias_atraso,
        "multa": multa,
        "adicional_diario": adicional,
        "encargos": encargos,
        "total": saldo + encargos,
    }
