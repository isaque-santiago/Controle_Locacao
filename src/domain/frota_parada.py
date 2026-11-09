"""Aba Frota do Dashboard: motos paradas, tempo parado e receita por moto. Funções puras, sem banco nem tela."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

MAX_PARADAS = 8
_MOTIVOS = {"manutencao": "Em manutenção", "disponivel": "Disponível"}


def _data(valor) -> Optional[date]:
    if not valor:
        return None
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def motos_paradas(motos: list[dict], contratos: list[dict], manutencoes: list[dict], hoje: date, limite: int = MAX_PARADAS) -> dict:
    """Motos que não estão rendendo: em manutenção (desde a entrada da ordem aberta mais antiga) ou disponíveis (desde o último contrato
    encerrado; sem contrato anterior, `desde` fica vazio). A lista vai da que está parada há mais tempo para a de menos tempo; as sem data ficam no fim."""
    linhas = []
    for m in motos:
        if m.get("status") == "manutencao":
            datas = [_data(o["data_entrada"]) for o in manutencoes if o["moto_id"] == m["id"] and o["status"] == "aberta"]
        elif m.get("status") == "disponivel":
            datas = [_data(c.get("data_encerramento")) for c in contratos if c["moto_id"] == m["id"] and c["status"] == "encerrado"]
            datas = [max(d for d in datas if d)] if any(datas) else []
        else:
            continue
        datas = [d for d in datas if d]
        desde = min(datas) if m["status"] == "manutencao" and datas else (datas[0] if datas else None)
        linhas.append({"moto_id": m["id"], "placa": m.get("placa") or "—", "motivo": _MOTIVOS[m["status"]], "desde": desde,
                       "dias": (hoje - desde).days if desde else None})
    linhas.sort(key=lambda l: (l["dias"] is None, -(l["dias"] or 0), l["placa"]))
    return {"linhas": linhas[:max(limite, 0)], "total": len(linhas)}


def tempo_parado_no_mes(manutencoes: list[dict], ativas: int, mes: date, hoje: date) -> dict:
    """Dias de moto na oficina no mês ÷ (motos ativas × dias do mês até hoje). Conta as ordens abertas (até hoje) e as concluídas (até a saída).
    `percentual` fica vazio sem motos ativas."""
    inicio = mes.replace(day=1)
    fim_do_mes = inicio.replace(day=monthrange(inicio.year, inicio.month)[1])
    fim = min(fim_do_mes, hoje)
    periodo = (fim - inicio).days + 1
    dias = 0
    for o in manutencoes:
        if o["status"] not in ("aberta", "concluida"):
            continue
        entrada = _data(o["data_entrada"])
        saida = _data(o.get("data_saida")) if o["status"] == "concluida" else None
        de, ate = max(entrada, inicio), min(saida or fim, fim)
        if ate >= de:
            dias += (ate - de).days + 1
    base = ativas * periodo
    percentual = (Decimal(100 * dias) / base).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if base > 0 else None
    return {"dias": dias, "percentual": percentual}


def receita_por_moto(receita, ativas: int) -> Optional[Decimal]:
    """Receita do mês ÷ motos ativas (as que podem render); vazio sem motos ativas."""
    if ativas <= 0:
        return None
    return (Decimal(str(receita or 0)) / ativas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
