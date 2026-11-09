"""Aba Hoje do Dashboard: quem cobrar agora e o que pede atenção. Funções puras, sem banco nem tela.

Uma linha por contrato, com tudo que está vencido (débito) e o que vence hoje, mais os encargos fixos de atraso.
Mesmas definições de `painel.cobrancas_de_hoje` (atrasadas e abertas que vencem hoje) e de `encargos.calcular_encargos`."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from src.domain.encargos import calcular_encargos
from src.domain.financeiro import DIAS_INADIMPLENTE, faixa_de_atraso
from src.domain.formatadores import formatar_moeda
from src.domain.painel import TOM_ATENCAO, TOM_PERIGO, ItemAlerta

MAX_COBRAR_AGORA = 8
FAIXA_HOJE = "hoje"
_ZERO = Decimal("0.00")


def _faixa(dias: int, corte: int) -> str:
    return FAIXA_HOJE if dias == 0 else faixa_de_atraso(dias, corte)


def analisar_cobranca(
    cobrancas: list[dict],
    nomes_clientes: dict,
    placas_motos: dict,
    multa_valor: Decimal,
    adicional_diario_valor: Decimal,
    hoje: date,
    corte: int = DIAS_INADIMPLENTE,
    limite: int = MAX_COBRAR_AGORA,
) -> dict:
    """O que cobrar hoje: por contrato, o débito vencido, o que vence hoje, os encargos e a cobrança mais antiga (a que o botão
    Pagar abre). A lista vem do maior atraso para o menor e, no mesmo atraso, do maior valor para o menor; os `limite` primeiros
    vão em `linhas` e `total_linhas` diz quantos contratos há ao todo.

    Totais: `a_cobrar` = vencido + vence hoje (sem encargos); `em_atraso` = só o vencido; `encargos` = multa + adicional fixos."""
    hoje_iso = hoje.isoformat()
    por_contrato = defaultdict(lambda: {"debito": _ZERO, "hoje": _ZERO, "encargos": _ZERO, "dias": 0, "cobranca_id": None, "primeiro": None})
    for c in cobrancas:
        saldo = Decimal(str(c.get("saldo") or 0))
        vencimento = str(c["vencimento"])[:10]
        atrasada = c.get("situacao") == "atrasada"
        vence_hoje = c.get("situacao") == "aberta" and vencimento == hoje_iso
        if saldo <= 0 or not (atrasada or vence_hoje):
            continue
        calculo = calcular_encargos(
            tipo=c["tipo"],
            saldo=saldo,
            vencimento=date.fromisoformat(vencimento),
            data_referencia=hoje,
            multa_valor=multa_valor,
            adicional_diario_valor=adicional_diario_valor,
        )
        item = por_contrato[(c["contrato_id"], c["cliente_id"], c["moto_id"])]
        item["debito" if atrasada else "hoje"] += saldo
        item["encargos"] += calculo["encargos"]
        item["dias"] = max(item["dias"], calculo["dias_atraso"])
        if item["primeiro"] is None or vencimento < item["primeiro"]:
            item["primeiro"], item["cobranca_id"] = vencimento, c.get("id")

    todas = [
        {
            "contrato_id": contrato,
            "cobranca_id": v["cobranca_id"],
            "cliente": nomes_clientes.get(cliente, "—"),
            "placa": placas_motos.get(moto, "—"),
            "dias_atraso": v["dias"],
            "faixa": _faixa(v["dias"], corte),
            "debito": v["debito"],
            "hoje": v["hoje"],
            "encargos": v["encargos"],
            "total": v["debito"] + v["hoje"] + v["encargos"],
        }
        for (contrato, cliente, moto), v in por_contrato.items()
    ]
    todas.sort(key=lambda l: (l["dias_atraso"], l["total"]), reverse=True)
    em_atraso = sum((l["debito"] for l in todas), _ZERO)
    vencem_hoje = sum((l["hoje"] for l in todas), _ZERO)
    return {
        "linhas": todas[: max(limite, 0)],
        "total_linhas": len(todas),
        "a_cobrar": em_atraso + vencem_hoje,
        "em_atraso": em_atraso,
        "vencem_hoje": vencem_hoje,
        "encargos": sum((l["encargos"] for l in todas), _ZERO),
        "contratos_em_atraso": sum(1 for l in todas if l["faixa"] == "em_atraso"),
        "contratos_inadimplentes": sum(1 for l in todas if l["faixa"] == "inadimplente"),
        "contratos_so_hoje": sum(1 for l in todas if l["faixa"] == FAIXA_HOJE),
    }


def parcelas_de_divida_atrasadas(parcelas: list[dict]) -> dict:
    """Quantas parcelas de dívida estão vencidas e não pagas, e quanto falta nelas (view `vw_parcelas_divida`)."""
    atrasadas = [p for p in parcelas if p.get("situacao") == "atrasada"]
    return {"quantidade": len(atrasadas), "valor": sum((Decimal(str(p.get("saldo") or 0)) for p in atrasadas), _ZERO)}


def atencao_financeira(parcelas_atrasadas: dict, a_repassar, entradas_sem_conta) -> list[ItemAlerta]:
    """Pendências de dinheiro que não são um indicador do topo: parcela de dívida vencida, despesa a repassar ao locatário e
    entrada do mês sem conta. Entram na mesma lista de `painel.agrupar_alertas`. `quantidade=None` mostra "!" no lugar do número."""
    itens = []
    if parcelas_atrasadas["quantidade"] > 0:
        itens.append(ItemAlerta(
            parcelas_atrasadas["quantidade"], "Parcela de dívida atrasada", f"{formatar_moeda(parcelas_atrasadas['valor'])} em atraso",
            TOM_PERIGO, "dividas"))
    repassar = Decimal(str(a_repassar or 0))
    if repassar > 0:
        itens.append(ItemAlerta(None, "Despesa a repassar ao locatário", formatar_moeda(repassar), TOM_ATENCAO, None))
    sem_conta = Decimal(str(entradas_sem_conta or 0))
    if sem_conta > 0:
        itens.append(ItemAlerta(None, "Entrada do mês sem conta", formatar_moeda(sem_conta), TOM_ATENCAO, None))
    return itens
