"""Próxima manutenção e situação do alerta (em_dia, proxima, vencida).

Mesma lógica usada pela view vw_alertas_manutencao no banco: replicada aqui
para poder ser testada isoladamente e usada em prévias na tela, antes de
gravar qualquer coisa.
"""

from datetime import date, timedelta
from typing import Optional


def calcular_proxima_manutencao(
    ultima_km: Optional[int],
    intervalo_km: Optional[int],
    ultima_data: Optional[date],
    intervalo_dias: Optional[int],
) -> dict:
    """Próxima km e próxima data de um item do plano (podem coexistir; o que
    vencer primeiro decide a situação em calcular_situacao)."""
    proxima_km = None
    if intervalo_km is not None:
        proxima_km = (ultima_km or 0) + intervalo_km

    proxima_data = None
    if intervalo_dias is not None and ultima_data is not None:
        proxima_data = ultima_data + timedelta(days=intervalo_dias)

    return {"proxima_km": proxima_km, "proxima_data": proxima_data}


def calcular_situacao(
    km_atual: int,
    proxima_km: Optional[int],
    hoje: date,
    proxima_data: Optional[date],
    alerta_km: int,
    alerta_dias: int,
) -> str:
    """Situação do alerta: 'vencida' (passou), 'proxima' (dentro do limite
    de alerta) ou 'em_dia'."""
    vencida = (proxima_km is not None and km_atual >= proxima_km) or (
        proxima_data is not None and hoje >= proxima_data
    )
    if vencida:
        return "vencida"

    proxima = (proxima_km is not None and proxima_km - km_atual <= alerta_km) or (
        proxima_data is not None and (proxima_data - hoje).days <= alerta_dias
    )
    if proxima:
        return "proxima"

    return "em_dia"
