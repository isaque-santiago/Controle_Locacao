"""Valores monetários e data local usados nos formulários."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


def hoje_br():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def decimal_br(valor, positivo=False):
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        numero = Decimal(texto)
        if (
            not numero.is_finite()
            or numero < 0
            or (positivo and numero == 0)
            or numero.as_tuple().exponent < -2
        ):
            raise ValueError
        return numero.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(
            "Informe um valor válido, sem negativos e com até duas casas decimais."
        ) from None
