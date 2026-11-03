"""Regras puras da página de Relatórios do frontend web: abas, visões e leitura do período."""

from datetime import date

ABAS = (
    ("resultado", "Resultado por moto"),
    ("custo", "Custo de manutenção"),
    ("inadimplencia", "Inadimplência"),
    ("fluxo", "Fluxo de caixa"),
)
VISOES_CUSTO = (("modelo", "Por modelo"), ("moto", "Por moto"))
MENSAGEM_PERIODO_INVERTIDO = "A data final deve ser igual ou posterior à inicial."


def aba_valida(valor: str | None) -> str:
    return valor if valor in dict(ABAS) else ABAS[0][0]


def visao_valida(valor: str | None) -> str:
    """Sem visão na URL o custo de manutenção abre por modelo, como no Streamlit."""
    return valor if valor in dict(VISOES_CUSTO) else VISOES_CUSTO[0][0]


def _data_ou_none(texto) -> date | None:
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def data_valida(texto) -> bool:
    return _data_ou_none(texto) is not None


def ler_periodo(de: str | None, ate: str | None, hoje: date) -> tuple[date, date, str | None]:
    """Período do relatório. Data ausente ou inválida vira o padrão (do dia 1º do mês até hoje); data final antes da
    inicial devolve a mensagem de erro, para a tela avisar em vez de calcular."""
    inicio = _data_ou_none(de) or hoje.replace(day=1)
    fim = _data_ou_none(ate) or hoje
    return inicio, fim, MENSAGEM_PERIODO_INVERTIDO if fim < inicio else None
