"""Entrada de dados dos formulários: normalização previsível e mensagens que dizem qual campo
corrigir e como (Plano de melhorias, Etapa 5).

Funções puras. As expressões regulares (`REGEX_*`) usam só a sintaxe comum a Python e
JavaScript, porque o Streamlit as aplica no navegador (`validate=`) e a mesma regra vale
no servidor, na hora de gravar.
"""

import re
from decimal import Decimal, InvalidOperation

# Aceita 1234,56 · 1.234,56 · 1234.56 · 1.234 · com "R$" opcional na frente.
REGEX_MOEDA = r"^\s*(R\$)?\s*\d{1,3}(\.\d{3})+(,\d{1,2})?\s*$|^\s*(R\$)?\s*\d+([.,]\d{1,2})?\s*$"
REGEX_CPF = r"^\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2}\s*$"
REGEX_TELEFONE = r"^\s*\(?\d{2}\)?\s*9?\d{4}-?\d{4}\s*$"
REGEX_PLACA = r"^\s*[A-Za-z]{3}-?\d[A-Za-z0-9]\d{2}\s*$"

_MILHAR_BR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def apenas_digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


# ---------------------------------------------------------------- exibição --


def texto_moeda(valor) -> str:
    """Valor inicial de um campo de dinheiro, no padrão brasileiro e sem o prefixo `R$`
    (o prefixo é desenhado ao lado do campo): 1234.5 -> '1.234,50'. Vazio ou inválido vira '0,00'."""
    try:
        numero = Decimal(str(valor if valor not in (None, "") else 0)).quantize(Decimal("0.01"))
    except InvalidOperation:
        numero = Decimal("0.00")
    inteiro, _, centavos = f"{numero:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"{sinal}{'.'.join(grupos)},{centavos}"


def texto_percentual(valor) -> str:
    """Percentual com vírgula e duas casas, sem o '%' (o sufixo fica ao lado do campo): 2 -> '2,00'."""
    return texto_moeda(valor).replace(".", "")


def formatar_cpf(texto) -> str:
    """'52998224725' -> '529.982.247-25'. Com outra quantidade de dígitos devolve o texto sem espaços
    nas pontas, para o usuário ver exatamente o que digitou ao corrigir."""
    numeros = apenas_digitos(texto)
    if len(numeros) != 11:
        return str(texto or "").strip()
    return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"


def formatar_telefone(texto) -> str:
    """'11912345678' -> '(11) 91234-5678'; '1134567890' -> '(11) 3456-7890'."""
    numeros = apenas_digitos(texto)
    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
    if len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return str(texto or "").strip()


def normalizar_placa(texto) -> str:
    """'abc-1d23 ' -> 'ABC1D23' (formato guardado no banco)."""
    return re.sub(r"[\s-]", "", str(texto or "")).upper()


def texto_placa(texto) -> str:
    """Placa como o usuário a lê: 'abc1d23' -> 'ABC-1D23'; incompleta fica só em maiúsculas."""
    placa = normalizar_placa(texto)
    return f"{placa[:3]}-{placa[3:]}" if len(placa) == 7 else placa


# ---------------------------------------------------------------- validação --


def decimal_campo(texto, rotulo, positivo=False) -> Decimal:
    """Converte o texto de um campo de dinheiro em Decimal, com erro que nomeia o campo e diz
    como corrigir. Aceita `1.234,56`, `1234,56`, `1234.56` e `1.500` (ponto de milhar)."""
    bruto = str(texto if texto is not None else "").strip().replace("R$", "").replace(" ", "")
    if not bruto:
        raise ValueError(f"{rotulo}: informe um valor, por exemplo 1.234,56.")
    if bruto.startswith("-"):
        raise ValueError(f"{rotulo}: o valor não pode ser negativo.")
    if "," in bruto:
        normalizado = bruto.replace(".", "").replace(",", ".")
    elif _MILHAR_BR.match(bruto):
        normalizado = bruto.replace(".", "")
    else:
        normalizado = bruto
    if not re.fullmatch(r"\d+(\.\d+)?", normalizado):
        raise ValueError(f"{rotulo}: use só números, com vírgula nos centavos (ex.: 1.234,56).")
    if len(normalizado.partition(".")[2]) > 2:
        raise ValueError(f"{rotulo}: use no máximo duas casas decimais (centavos).")
    numero = Decimal(normalizado).quantize(Decimal("0.01"))
    if positivo and numero == 0:
        raise ValueError(f"{rotulo}: informe um valor maior que zero.")
    return numero


def inteiro_campo(texto, rotulo, minimo=0, maximo=None) -> int:
    """Número inteiro de um campo de texto (dias, quantidades), com erro que nomeia o campo."""
    bruto = str(texto if texto is not None else "").strip()
    if not re.fullmatch(r"\d+", bruto):
        raise ValueError(f"{rotulo}: use só números inteiros, sem vírgula nem sinal.")
    numero = int(bruto)
    if numero < minimo:
        raise ValueError(f"{rotulo}: o menor valor aceito é {minimo}.")
    if maximo is not None and numero > maximo:
        raise ValueError(f"{rotulo}: o maior valor aceito é {maximo}.")
    return numero


def erro_de(funcao, *args, **kwargs):
    """Mensagem do `ValueError` que a validação levantaria, ou None quando a entrada é válida.
    Serve para decidir, a cada reexecução, se a confirmação fica disponível e por quê."""
    try:
        funcao(*args, **kwargs)
    except ValueError as erro:
        return str(erro)
    return None


def primeiro_erro(*mensagens):
    """Primeira mensagem de erro não vazia (ordem de leitura do formulário), ou None."""
    return next((m for m in mensagens if m), None)
