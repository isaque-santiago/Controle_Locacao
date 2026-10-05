"""Regras da troca de óleo reportada pelo locatário (Fase 7).

Mesma lógica da RPC rpc_registrar_troca_oleo_locatario no banco: replicada aqui
para validar o formulário e mostrar a prévia (multa ou não) antes de gravar.
A multa é um valor fixo único, definido em Configurações.
"""

from decimal import Decimal
from typing import Optional

from src.domain.manutencao_regras import calcular_proxima_manutencao

PAPEL_DONO = "dono"
PAPEL_LOCATARIO = "locatario"


def validar_km_informado(texto) -> int:
    """Converte o hodômetro digitado em inteiro não negativo."""
    limpo = str(texto or "").strip().replace(".", "")
    if not limpo.isdigit():
        raise ValueError("Informe o hodômetro apenas com números, em km.")
    return int(limpo)


def avaliar_troca_oleo(
    km_informado: int,
    km_atual: int,
    ultima_km: Optional[int],
    intervalo_km: Optional[int],
    valor_multa: Decimal = Decimal("0.00"),
) -> dict:
    """Confere o km informado e diz se a troca passou do intervalo do plano.

    O km nunca regride: informado < km_atual é erro. Passou do intervalo quando
    km_informado > próxima km (ultima_km + intervalo_km); trocar exatamente na
    quilometragem prevista não gera multa. Sem valor de multa configurado (0),
    o excesso é apontado mas nada é cobrado.
    """
    if km_informado < km_atual:
        raise ValueError(
            f"O hodômetro não pode ser menor que o último registrado ({km_atual} km)."
        )

    proxima_km = calcular_proxima_manutencao(ultima_km, intervalo_km, None, None)[
        "proxima_km"
    ]
    excedeu = proxima_km is not None and km_informado > proxima_km
    return {
        "proxima_km": proxima_km,
        "excedeu": excedeu,
        "km_excedente": km_informado - proxima_km if excedeu else 0,
        "multa": Decimal(valor_multa).quantize(Decimal("0.01")) if excedeu else Decimal("0.00"),
    }
