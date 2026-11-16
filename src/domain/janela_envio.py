"""Horários de envio das mensagens de WhatsApp (seção 20 do plano; horários definidos pelo dono em 17/11/2026).

As mensagens saem em **três disparos por dia**, às 7:30, 11:30 e 15:00 (fuso America/Sao_Paulo), de segunda a sábado e
sem feriados nacionais. Cada disparo fica aberto por `DURACAO_DO_DISPARO` (as rodadas do script, a cada 15 a 30 minutos,
vão esvaziando a fila nesse tempo). O que for devido fora de um disparo espera o seguinte.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.domain.feriados import eh_feriado

FUSO = ZoneInfo("America/Sao_Paulo")
HORARIOS_DE_DISPARO = (time(7, 30), time(11, 30), time(15, 0))
DURACAO_DO_DISPARO = timedelta(minutes=60)
_DOMINGO = 6


def dia_de_envio(dia: date) -> bool:
    """Segunda a sábado e fora de feriado nacional."""
    return dia.weekday() != _DOMINGO and not eh_feriado(dia)


def _em_br(momento: datetime) -> datetime:
    if momento.tzinfo is None:
        raise ValueError("Informe a data e hora com fuso horário.")
    return momento.astimezone(FUSO)


def _inicio(dia: date, horario: time) -> datetime:
    return datetime.combine(dia, horario, tzinfo=FUSO)


def dentro_da_janela(momento: datetime) -> bool:
    """O momento cai dentro de um dos três disparos do dia (do horário até `DURACAO_DO_DISPARO` depois)."""
    local = _em_br(momento)
    if not dia_de_envio(local.date()):
        return False
    return any(_inicio(local.date(), h) <= local < _inicio(local.date(), h) + DURACAO_DO_DISPARO for h in HORARIOS_DE_DISPARO)


def proximo_dia_de_envio(dia: date) -> date:
    """O próprio `dia`, se tiver envio; senão o primeiro dia de envio depois dele."""
    while not dia_de_envio(dia):
        dia += timedelta(days=1)
    return dia


def dia_de_envio_anterior(dia: date) -> date:
    """O último dia de envio ANTES de `dia` (estritamente anterior)."""
    dia -= timedelta(days=1)
    while not dia_de_envio(dia):
        dia -= timedelta(days=1)
    return dia


def proximo_horario_valido(momento: datetime) -> datetime:
    """O próprio momento, se estiver num disparo; senão o início do próximo disparo (hoje ou no próximo dia de envio)."""
    local = _em_br(momento)
    if dentro_da_janela(local):
        return local
    dia = local.date()
    if dia_de_envio(dia):
        for horario in HORARIOS_DE_DISPARO:
            if _inicio(dia, horario) > local:
                return _inicio(dia, horario)
    return _inicio(proximo_dia_de_envio(dia + timedelta(days=1)), HORARIOS_DE_DISPARO[0])
