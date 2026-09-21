"""Geração das datas e valores das cobranças de um contrato."""

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

_INCREMENTOS = {
    "diario": relativedelta(days=1),
    "semanal": relativedelta(weeks=1),
    "quinzenal": relativedelta(days=15),
    "mensal": relativedelta(months=1),
}


def _proximo_vencimento(vencimento: date, periodicidade: str) -> date:
    return vencimento + _INCREMENTOS[periodicidade]


def gerar_agenda(
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: date,
) -> list:
    """Agenda de cobranças de locação de um contrato com prazo definido.

    A 1ª parcela vence em data_inicio (pagamento antecipado do período); as
    demais somam a periodicidade ao vencimento anterior até data_fim_prevista
    (inclusive). Em "mensal", meses curtos usam o último dia do mês.
    """
    if periodicidade not in _INCREMENTOS:
        raise ValueError(f"Periodicidade inválida: {periodicidade!r}")
    if data_fim_prevista < data_inicio:
        raise ValueError("data_fim_prevista não pode ser anterior a data_inicio.")

    agenda = []
    vencimento = data_inicio
    numero = 1
    while vencimento <= data_fim_prevista:
        agenda.append({"numero": numero, "vencimento": vencimento, "valor": valor_periodo})
        numero += 1
        vencimento = _proximo_vencimento(vencimento, periodicidade)

    return agenda
