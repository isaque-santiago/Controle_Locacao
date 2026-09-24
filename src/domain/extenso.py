"""Números, valores em reais e datas por extenso (pt-BR), para o contrato."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

_UNIDADES = (
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
    "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
    "dezoito", "dezenove",
)
_DEZENAS = (
    "", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
    "oitenta", "noventa",
)
_CENTENAS = (
    "", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
    "setecentos", "oitocentos", "novecentos",
)
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
    "setembro", "outubro", "novembro", "dezembro",
)


def _ate_999(n: int) -> str:
    if n == 100:
        return "cem"
    centenas, resto = divmod(n, 100)
    partes = []
    if centenas:
        partes.append(_CENTENAS[centenas])
    if resto:
        if resto < 20:
            partes.append(_UNIDADES[resto])
        else:
            dezena, unidade = divmod(resto, 10)
            partes.append(
                _DEZENAS[dezena] + (f" e {_UNIDADES[unidade]}" if unidade else "")
            )
    return " e ".join(partes)


def inteiro_por_extenso(n: int) -> str:
    """Número inteiro não negativo, até 999 bilhões."""
    if n < 0 or n >= 10**12:
        raise ValueError("Número fora do intervalo suportado.")
    if n == 0:
        return "zero"
    blocos = []  # (texto, valor do bloco)
    resto = n
    for escala, singular, plural in (
        (10**9, "bilhão", "bilhões"),
        (10**6, "milhão", "milhões"),
        (10**3, "mil", "mil"),
    ):
        quociente, resto = divmod(resto, escala)
        if not quociente:
            continue
        if escala == 10**3:
            texto = "mil" if quociente == 1 else f"{_ate_999(quociente)} mil"
        else:
            texto = f"{_ate_999(quociente)} {singular if quociente == 1 else plural}"
        blocos.append((texto, quociente))
    if resto:
        blocos.append((_ate_999(resto), resto))
    if len(blocos) == 1:
        return blocos[0][0]
    # "e" antes do último bloco quando ele é menor que 100 ou centena exata
    ultimo_texto, ultimo_valor = blocos[-1]
    anteriores = " ".join(texto for texto, _ in blocos[:-1])
    conector = " e " if ultimo_valor < 100 or ultimo_valor % 100 == 0 else " "
    return f"{anteriores}{conector}{ultimo_texto}"


def moeda_por_extenso(valor) -> str:
    """Ex.: 280 -> 'duzentos e oitenta reais'; 1,5 -> 'um real e cinquenta centavos'."""
    numero = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if numero < 0:
        raise ValueError("Valor negativo não tem extenso monetário.")
    reais = int(numero)
    centavos = int((numero - reais) * 100)
    if reais == 0 and centavos == 0:
        return "zero real"
    partes = []
    if reais:
        texto = inteiro_por_extenso(reais)
        if reais >= 10**6 and reais % 10**6 == 0:
            texto += " de reais"
        else:
            texto += " real" if reais == 1 else " reais"
        partes.append(texto)
    if centavos:
        partes.append(
            inteiro_por_extenso(centavos) + (" centavo" if centavos == 1 else " centavos")
        )
    return " e ".join(partes)


def data_por_extenso(data: date) -> str:
    """Ex.: 11/02/2026 -> '11 de fevereiro de 2026'."""
    return f"{data.day:02d} de {_MESES[data.month - 1]} de {data.year}"
