"""Número de WhatsApp no formato da Evolution API: 55 + DDD + número, só dígitos (seção 20 do plano).

Aceita o que o dono digita no cadastro ("(11) 98888-7777", "011 98888-7777", "+55 11 98888-7777") e devolve
`5511988887777`. Número que não parece celular brasileiro devolve None (o aviso fica `ignorada` e o dono vê no sistema).
Se o número realmente tem WhatsApp, quem confirma é a Evolution, na hora do envio.
"""

import re


def normalizar_numero(texto) -> str | None:
    digitos = re.sub(r"\D", "", str(texto or ""))
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    elif digitos.startswith("0"):
        digitos = digitos.lstrip("0")  # prefixo de operadora ou de interurbano
    if len(digitos) not in (10, 11):
        return None
    ddd = int(digitos[:2])
    if not 11 <= ddd <= 99:
        return None
    assinante = digitos[2:]
    if len(assinante) == 9 and assinante[0] != "9":
        return None
    if len(assinante) == 8 and assinante[0] in "2345":
        return None  # telefone fixo: não recebe WhatsApp
    return "55" + digitos


def formatar_numero(numero) -> str:
    """5511988887777 -> (11) 98888-7777, para a tela; o que não for um número normalizado volta como veio."""
    texto = str(numero or "")
    if not re.fullmatch(r"55\d{10,11}", texto):
        return texto
    ddd, assinante = texto[2:4], texto[4:]
    return f"({ddd}) {assinante[:-4]}-{assinante[-4:]}"
