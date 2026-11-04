"""Regras do Dashboard financeiro (mês, caixa, devedores). Funções puras, sem banco nem tela.

Mesmas definições da RPC `rpc_resumo_financeiro`:
  resultado = receita - despesas (custo operacional, sem investimento em veículo);
  caixa     = receita - despesas - investimento - parcelas de dívida - retiradas + aportes.
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from src.domain.encargos import calcular_encargos

# A partir de quantos dias de atraso o contrato passa de "em atraso" para "inadimplente".
DIAS_INADIMPLENTE = 15
MAX_DEVEDORES = 8
_ZERO = Decimal("0.00")
_CENTAVOS = Decimal("0.01")
_MESES_CURTOS = ("jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez.")
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _dinheiro(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def primeiro_dia(data: date) -> date:
    return data.replace(day=1)


def mes_da_consulta(texto: Optional[str], hoje: date) -> date:
    """Primeiro dia do mês pedido em `aaaa-mm`. Vazio, inválido ou futuro vale o mês de hoje."""
    atual = primeiro_dia(hoje)
    try:
        ano, mes = str(texto or "").strip().split("-")
        pedido = date(int(ano), int(mes), 1)
    except ValueError:
        return atual
    return atual if pedido > atual else pedido


def somar_meses(mes: date, quantidade: int) -> date:
    indice = mes.year * 12 + (mes.month - 1) + quantidade
    return date(indice // 12, indice % 12 + 1, 1)


def rotulo_mes(mes: date) -> str:
    return f"{_MESES[mes.month - 1]} de {mes.year}"


def rotulo_mes_curto(mes: date) -> str:
    return f"{_MESES_CURTOS[mes.month - 1]}/{str(mes.year)[2:]}"


def consolidar_mes(bruto: dict) -> dict:
    """Totais de um mês da RPC (texto ou número) em Decimal, com resultado, caixa e margem."""
    receita = _dinheiro(bruto.get("receita"))
    despesas = _dinheiro(bruto.get("despesas"))
    investimento = _dinheiro(bruto.get("investimento"))
    parcelas = _dinheiro(bruto.get("parcelas_divida"))
    retiradas = _dinheiro(bruto.get("retiradas"))
    aportes = _dinheiro(bruto.get("aportes"))
    resultado = receita - despesas
    return {
        "mes": date.fromisoformat(str(bruto["mes"])[:10]),
        "receita": receita,
        "despesas": despesas,
        "investimento": investimento,
        "parcelas_divida": parcelas,
        "retiradas": retiradas,
        "aportes": aportes,
        "resultado": resultado,
        "caixa": resultado - investimento - parcelas - retiradas + aportes,
        "margem": margem(receita, resultado),
    }


def margem(receita: Decimal, resultado: Decimal) -> Optional[int]:
    """Resultado como % da receita, arredondado; None sem receita."""
    if receita <= 0:
        return None
    return int((resultado * 100 / receita).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def receita_mensal_estimada(semanal: Decimal, mensal: Decimal) -> Decimal:
    """Contratos semanais valem 52/12 semanas por mês; os mensais entram como estão."""
    return (Decimal(str(semanal or 0)) * 52 / 12 + Decimal(str(mensal or 0))).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def faixa_de_atraso(dias: int, corte: int = DIAS_INADIMPLENTE) -> str:
    """'em_atraso' (até corte-1 dias) ou 'inadimplente' (corte dias ou mais)."""
    return "inadimplente" if dias >= corte else "em_atraso"


def analisar_devedores(
    cobrancas: list[dict],
    nomes_clientes: dict,
    placas_motos: dict,
    multa_valor: Decimal,
    adicional_diario_valor: Decimal,
    hoje: date,
    corte: int = DIAS_INADIMPLENTE,
    limite: int = MAX_DEVEDORES,
) -> dict:
    """Quem deve hoje: débito (saldo vencido), encargos de atraso e ranking por contrato.

    Só entram cobranças atrasadas e com saldo. Cada contrato tem um único dia de atraso, o da
    cobrança mais antiga em aberto. O ranking traz os `limite` maiores (débito + encargos)."""
    por_contrato = defaultdict(lambda: {"debito": _ZERO, "encargos": _ZERO, "dias": 0})
    for c in cobrancas:
        saldo = Decimal(str(c.get("saldo") or 0))
        if c.get("situacao") != "atrasada" or saldo <= 0:
            continue
        calculo = calcular_encargos(
            tipo=c["tipo"],
            saldo=saldo,
            vencimento=date.fromisoformat(str(c["vencimento"])[:10]),
            data_referencia=hoje,
            multa_valor=multa_valor,
            adicional_diario_valor=adicional_diario_valor,
        )
        item = por_contrato[(c["contrato_id"], c["cliente_id"], c["moto_id"])]
        item["debito"] += saldo
        item["encargos"] += calculo["encargos"]
        item["dias"] = max(item["dias"], calculo["dias_atraso"])

    linhas = [
        {
            "contrato_id": contrato,
            "cliente": nomes_clientes.get(cliente, "—"),
            "placa": placas_motos.get(moto, "—"),
            "dias_atraso": v["dias"],
            "faixa": faixa_de_atraso(v["dias"], corte),
            "debito": v["debito"],
            "encargos": v["encargos"],
            "total": v["debito"] + v["encargos"],
        }
        for (contrato, cliente, moto), v in por_contrato.items()
    ]
    linhas.sort(key=lambda l: (l["total"], l["dias_atraso"]), reverse=True)
    return {
        "a_receber": sum((l["debito"] for l in linhas), _ZERO),
        "encargos": sum((l["encargos"] for l in linhas), _ZERO),
        "contratos_em_aberto": len(linhas),
        "em_atraso": sum(1 for l in linhas if l["faixa"] == "em_atraso"),
        "inadimplentes": sum(1 for l in linhas if l["faixa"] == "inadimplente"),
        "ranking": linhas[:limite],
    }


def saldo_das_dividas(saldos: list[dict]) -> dict:
    """Saldo em aberto das dívidas (o confirmado pelo responsável, senão o calculado) e o total de motos fiado."""
    total = _ZERO
    fiado = _ZERO
    for s in saldos:
        confirmado = s.get("saldo_confirmado")
        saldo = Decimal(str(confirmado if confirmado is not None else s.get("saldo_calculado") or 0))
        saldo = max(saldo, _ZERO)
        total += saldo
        if s.get("tipo") == "moto_fiado":
            fiado += saldo
    return {"total": total, "moto_fiado": fiado}

