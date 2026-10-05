"""Validação dos parâmetros do sistema e exemplo de encargos da tela Configurações."""

from datetime import date, timedelta
from decimal import Decimal

from src.domain.encargos import calcular_encargos
from src.domain.valores import decimal_br

CAMPOS_INTEIROS = {
    "alerta_manutencao_km": "Avisar (km antes)",
    "alerta_manutencao_dias": "Avisar (dias antes)",
    "alerta_documento_dias": "Documentos da moto",
    "alerta_cnh_dias": "CNH do cliente",
}
CAMPOS_MONETARIOS = {
    "multa_atraso_valor": "Multa de atraso (no vencimento)",
    "encargo_diario_valor": "Adicional por dia de atraso",
    "multa_troca_oleo_valor": "Multa por troca de óleo fora do intervalo",
}
LIMITE_INTEIRO = 100_000


def _inteiro(valor, rotulo):
    texto = str(valor).strip()
    if not texto.isdigit() or int(texto) > LIMITE_INTEIRO:
        raise ValueError(f"{rotulo}: informe um número inteiro entre 0 e {LIMITE_INTEIRO}.")
    return int(texto)


def campos_alterados(antes: dict, depois: dict) -> list[str]:
    """Rótulos dos parâmetros cujo valor mudou (comparação numérica: `2` e `2.00` são o mesmo valor).
    Campos ausentes em qualquer um dos lados são ignorados."""
    rotulos = {**CAMPOS_MONETARIOS, **CAMPOS_INTEIROS}
    alterados = []
    for campo, rotulo in rotulos.items():
        if campo in antes and campo in depois and antes[campo] is not None and depois[campo] is not None:
            if Decimal(str(antes[campo])) != Decimal(str(depois[campo])):
                alterados.append(rotulo)
    return alterados


def validar_configuracao(entrada: dict) -> dict:
    """Converte o que foi digitado (texto pt-BR) nos tipos do banco.

    Valores em reais (multas e adicional diário): Decimal com 2 casas, não negativo,
    enviado como texto. Demais campos: inteiros não negativos.
    """
    dados = {}
    for campo, rotulo in CAMPOS_MONETARIOS.items():
        try:
            dados[campo] = str(decimal_br(entrada[campo]))
        except ValueError:
            raise ValueError(
                f"{rotulo}: informe um valor em reais válido, com até duas casas decimais."
            ) from None
    for campo, rotulo in CAMPOS_INTEIROS.items():
        dados[campo] = _inteiro(entrada[campo], rotulo)
    return dados


def exemplo_encargos(
    multa_valor, adicional_diario_valor, saldo=Decimal("500.00"), dias_vencida=5
) -> dict:
    """Exemplo do cartão de encargos: locação de `saldo` vencida há `dias_vencida` dias."""
    referencia = date(2000, 1, 1) + timedelta(days=dias_vencida)
    return {
        "saldo": saldo,
        "dias_vencida": dias_vencida,
        **calcular_encargos(
            "locacao",
            saldo,
            date(2000, 1, 1),
            referencia,
            Decimal(str(multa_valor)),
            Decimal(str(adicional_diario_valor)),
        ),
    }
