"""Janela de envio das mensagens de WhatsApp (seção 20 do plano).

De segunda a sábado, das 8h às 19h (fuso America/Sao_Paulo), sem feriados nacionais. O que cair fora da
janela vai para o primeiro horário válido seguinte.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.domain.feriados import eh_feriado

FUSO = ZoneInfo("America/Sao_Paulo")
ABERTURA = time(8, 0)
FECHAMENTO = time(19, 0)  # o envio vai até 18h59; às 19h já está fora
_DOMINGO = 6


def dia_de_envio(dia: date) -> bool:
    """Segunda a sábado e fora de feriado nacional."""
    return dia.weekday() != _DOMINGO and not eh_feriado(dia)


def _em_br(momento: datetime) -> datetime:
    if momento.tzinfo is None:
        raise ValueError("Informe a data e hora com fuso horário.")
    return momento.astimezone(FUSO)


def dentro_da_janela(momento: datetime) -> bool:
    local = _em_br(momento)
    return dia_de_envio(local.date()) and ABERTURA <= local.time() < FECHAMENTO


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
    """O próprio momento, se estiver na janela; senão a abertura seguinte (8h do próximo dia de envio)."""
    local = _em_br(momento)
    if dentro_da_janela(local):
        return local
    dia = local.date()
    if dia_de_envio(dia) and local.time() < ABERTURA:
        return datetime.combine(dia, ABERTURA, tzinfo=FUSO)
    return datetime.combine(proximo_dia_de_envio(dia + timedelta(days=1)), ABERTURA, tzinfo=FUSO)


def liberado_ate(momento: datetime, folga: timedelta = timedelta(minutes=25)) -> datetime | None:
    """Até quando o envio fica liberado a partir de `momento`: `folga` à frente, mas nunca depois do fechamento da janela.

    É o "portão" que o preparo grava no banco; quem só envia (o script ou o n8n) não decide horário nenhum. Fora da janela
    (noite, domingo, feriado) devolve None: portão fechado."""
    local = _em_br(momento)
    if not dentro_da_janela(local):
        return None
    return min(local + folga, datetime.combine(local.date(), FECHAMENTO, tzinfo=FUSO))

