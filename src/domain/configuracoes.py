"""Validação dos parâmetros do sistema e exemplo de encargos da tela Configurações."""

from datetime import date, timedelta
from decimal import Decimal

from src.domain.encargos import calcular_encargos
from src.domain.valores import decimal_br

CAMPOS_PERCENTUAIS = {
    "multa_atraso_percentual": "Multa por atraso",
    "juros_mensal_percentual": "Juros mensal",
}
CAMPOS_INTEIROS = {
    "carencia_dias": "Carência",
    "alerta_manutencao_km": "Avisar (km antes)",
    "alerta_manutencao_dias": "Avisar (dias antes)",
    "alerta_documento_dias": "Documentos da moto",
    "alerta_cnh_dias": "CNH do cliente",
}
_LIMITE_INTEIRO = 100_000


def _inteiro(valor, rotulo):
    texto = str(valor).strip()
    if not texto.isdigit() or int(texto) > _LIMITE_INTEIRO:
        raise ValueError(f"{rotulo}: informe um número inteiro entre 0 e {_LIMITE_INTEIRO}.")
    return int(texto)


def validar_configuracao(entrada: dict) -> dict:
    """Converte o que foi digitado (texto pt-BR) nos tipos do banco.

    Percentuais: Decimal com 2 casas entre 0 e 100, enviados como texto.
    Demais campos: inteiros não negativos.
    """
    dados = {}
    for campo, rotulo in CAMPOS_PERCENTUAIS.items():
        try:
            valor = decimal_br(entrada[campo])
        except ValueError:
            raise ValueError(
                f"{rotulo}: informe um percentual válido, com até duas casas decimais."
            ) from None
        if valor > 100:
            raise ValueError(f"{rotulo}: o percentual não pode passar de 100%.")
        dados[campo] = str(valor)
    for campo, rotulo in CAMPOS_INTEIROS.items():
        dados[campo] = _inteiro(entrada[campo], rotulo)
    return dados


def exemplo_encargos(
    multa_percentual, juros_percentual, carencia_dias, saldo=Decimal("500.00"), dias_vencida=5
) -> dict:
    """Exemplo do cartão de encargos: cobrança de `saldo` vencida há `dias_vencida` dias."""
    referencia = date(2000, 1, 1) + timedelta(days=dias_vencida)
    return {
        "saldo": saldo,
        "dias_vencida": dias_vencida,
        **calcular_encargos(
            saldo,
            date(2000, 1, 1),
            referencia,
            Decimal(str(multa_percentual)),
            Decimal(str(juros_percentual)),
            int(carencia_dias),
        ),
    }
