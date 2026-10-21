"""Geração das datas e valores das cobranças de um contrato."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta

_INCREMENTOS = {
    "diario": relativedelta(days=1),
    "semanal": relativedelta(weeks=1),
    "quinzenal": relativedelta(days=15),
    "mensal": relativedelta(months=1),
}

# Janela da agenda de um contrato por prazo indeterminado: a mesma que a RPC
# `rpc_criar_contrato` usa na criação (data_inicio + 30 dias). As cobranças seguintes
# são geradas por `rpc_gerar_cobrancas_pendentes` enquanto o contrato estiver ativo.
HORIZONTE_INDETERMINADO_DIAS = 30


def _proximo_vencimento(vencimento: date, periodicidade: str) -> date:
    return vencimento + _INCREMENTOS[periodicidade]


def gerar_agenda(
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: Optional[date] = None,
    *,
    numero_parcelas: Optional[int] = None,
    parcelas_pagas_inicial: int = 0,
    primeira_cobranca: Optional[date] = None,
) -> list:
    """Agenda de cobranças de locação de um contrato.

    A 1ª parcela vence em data_inicio (pagamento antecipado do período); as
    demais somam a periodicidade ao vencimento anterior. Em "mensal", meses
    curtos usam o último dia do mês.

    Com `data_fim_prevista`, gera todas as parcelas até essa data (inclusive).
    Sem ela (contrato por prazo indeterminado, a regra da operação), gera só a
    janela inicial de HORIZONTE_INDETERMINADO_DIAS dias a partir de data_inicio.

    Promessa de compra e contratos importados (mesma regra de `rpc_criar_contrato`):
    - `primeira_cobranca` ancora a 1ª parcela (padrão: data_inicio);
    - a numeração parte de `parcelas_pagas_inicial + 1`;
    - com `numero_parcelas`, a agenda para na última parcela do contrato.
    """
    if periodicidade not in _INCREMENTOS:
        raise ValueError(f"Periodicidade inválida: {periodicidade!r}")
    if data_fim_prevista is not None and data_fim_prevista < data_inicio:
        raise ValueError("data_fim_prevista não pode ser anterior a data_inicio.")
    if numero_parcelas is not None and numero_parcelas <= 0:
        raise ValueError("numero_parcelas deve ser positivo.")
    if parcelas_pagas_inicial < 0:
        raise ValueError("parcelas_pagas_inicial não pode ser negativo.")
    if numero_parcelas is not None and parcelas_pagas_inicial > numero_parcelas:
        raise ValueError("As parcelas já pagas não podem superar o número de parcelas.")

    limite = (
        data_fim_prevista
        if data_fim_prevista is not None
        else data_inicio + timedelta(days=HORIZONTE_INDETERMINADO_DIAS)
    )
    agenda = []
    vencimento = primeira_cobranca or data_inicio
    numero = parcelas_pagas_inicial + 1
    while vencimento <= limite and (numero_parcelas is None or numero <= numero_parcelas):
        agenda.append({"numero": numero, "vencimento": vencimento, "valor": valor_periodo})
        numero += 1
        vencimento = _proximo_vencimento(vencimento, periodicidade)

    return agenda
