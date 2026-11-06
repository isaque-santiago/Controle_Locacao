"""Feriados nacionais do Brasil (envio de WhatsApp: seção 20 do plano).

Só os nacionais, calculados pelo ano: os fixos mais os que dependem da Páscoa (Carnaval, Sexta-feira Santa e
Corpus Christi). Feriados estaduais e municipais ficam de fora, por decisão do dono. A Páscoa cai sempre num
domingo, que já não tem envio, então não entra na lista.
"""

from datetime import date, timedelta

from dateutil.easter import easter

_FIXOS = (
    (1, 1, "Confraternização Universal"),
    (4, 21, "Tiradentes"),
    (5, 1, "Dia do Trabalho"),
    (9, 7, "Independência do Brasil"),
    (10, 12, "Nossa Senhora Aparecida"),
    (11, 2, "Finados"),
    (11, 15, "Proclamação da República"),
    (11, 20, "Consciência Negra"),
    (12, 25, "Natal"),
)


def feriados_nacionais(ano: int) -> dict[date, str]:
    """Data -> nome dos feriados nacionais do `ano` (inclui segunda e terça de Carnaval)."""
    feriados = {date(ano, mes, dia): nome for mes, dia, nome in _FIXOS}
    pascoa = easter(ano)
    feriados[pascoa - timedelta(days=48)] = "Carnaval (segunda-feira)"
    feriados[pascoa - timedelta(days=47)] = "Carnaval (terça-feira)"
    feriados[pascoa - timedelta(days=2)] = "Sexta-feira Santa"
    feriados[pascoa + timedelta(days=60)] = "Corpus Christi"
    return feriados


def eh_feriado(dia: date) -> bool:
    return dia in feriados_nacionais(dia.year)
