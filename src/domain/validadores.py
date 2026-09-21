"""Validação de CPF, placa (antiga e Mercosul) e telefone."""

import re


def _apenas_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def _digito_verificador_cpf(base: str) -> str:
    peso_inicial = len(base) + 1
    soma = sum(int(digito) * peso for digito, peso in zip(base, range(peso_inicial, 1, -1)))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def validar_cpf(cpf: str) -> bool:
    """Valida CPF pelos dígitos verificadores. Aceita com ou sem máscara."""
    numeros = _apenas_digitos(cpf)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False

    primeiro_digito = _digito_verificador_cpf(numeros[:9])
    segundo_digito = _digito_verificador_cpf(numeros[:9] + primeiro_digito)
    return numeros[9:] == primeiro_digito + segundo_digito


_PADRAO_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}[0-9]{4}$")
_PADRAO_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")


def validar_placa(placa: str) -> bool:
    """Valida placa nos formatos antigo (ABC1234) e Mercosul (ABC1D23)."""
    normalizada = (placa or "").strip().upper().replace("-", "")
    return bool(
        _PADRAO_PLACA_ANTIGA.match(normalizada) or _PADRAO_PLACA_MERCOSUL.match(normalizada)
    )


def validar_telefone(telefone: str) -> bool:
    """Valida telefone brasileiro (fixo com DDD: 10 dígitos; celular com DDD: 11 dígitos)."""
    numeros = _apenas_digitos(telefone)
    if len(numeros) not in (10, 11):
        return False

    ddd = int(numeros[:2])
    if ddd < 11 or ddd > 99:
        return False

    if len(numeros) == 11 and numeros[2] != "9":
        return False

    return True
