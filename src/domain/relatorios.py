"""Consolida finanças com Decimal, sem duplicar receitas por junções."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.domain.encargos import calcular_encargos


def valor(numero):
    return Decimal(str(numero or 0))


def consolidar(
    motos,
    contratos,
    cobrancas,
    pagamentos,
    manutencoes,
    documentos,
    historico,
    inicio,
    fim,
):
    contratos_por_id = {c["id"]: c for c in contratos}
    cobrancas_por_id = {c["id"]: c for c in cobrancas}
    resultado = {
        m["id"]: {
            "moto_id": m["id"],
            "placa": m["placa"],
            "modelo": m["modelo"],
            "receita_recebida": Decimal(0),
            "custo_manutencao": Decimal(0),
            "custo_documentos": Decimal(0),
        }
        for m in motos
    }
    fluxo = defaultdict(
        lambda: {
            "receita_recebida": Decimal(0),
            "custo_manutencao": Decimal(0),
            "custo_documentos": Decimal(0),
        }
    )

    def dentro(data):
        return bool(data) and inicio.isoformat() <= str(data)[:10] <= fim.isoformat()

    for p in pagamentos:
        c = cobrancas_por_id.get(p["cobranca_id"])
        if not c or c["tipo"] == "caucao" or not dentro(p["data_pagamento"]):
            continue
        moto = contratos_por_id[c["contrato_id"]]["moto_id"]
        total = valor(p["valor"]) + valor(p["multa_juros"])
        resultado[moto]["receita_recebida"] += total
        fluxo[p["data_pagamento"][:7]]["receita_recebida"] += total
    for registros, campo, data_campo, aceita in [
        (
            manutencoes,
            "custo_manutencao",
            "data_entrada",
            lambda m: m["status"] == "concluida",
        ),
        (
            documentos,
            "custo_documentos",
            "data_regularizacao",
            lambda d: d["regularizado"],
        ),
    ]:
        for r in registros:
            data = r.get(data_campo)
            if aceita(r) and dentro(data):
                total = valor(
                    r.get("custo_total")
                    if campo == "custo_manutencao"
                    else r.get("valor")
                )
                resultado[r["moto_id"]][campo] += total
                fluxo[data[:7]][campo] += total
    for id, r in resultado.items():
        leituras = [
            h for h in historico if h["moto_id"] == id and h["data"] <= fim.isoformat()
        ]
        antes = [h["km"] for h in leituras if h["data"] <= inicio.isoformat()]
        durante = [h["km"] for h in leituras if dentro(h["data"])]
        base = max(antes) if antes else min(durante, default=0)
        r["km_rodados"] = max(max((h["km"] for h in leituras), default=base) - base, 0)
        r["custo_por_km"] = (
            (r["custo_manutencao"] / r["km_rodados"]).quantize(Decimal("0.01"))
            if r["km_rodados"]
            else None
        )
        r["resultado"] = (
            r["receita_recebida"] - r["custo_manutencao"] - r["custo_documentos"]
        )
    meses = []
    for mes, r in sorted(fluxo.items()):
        meses.append(
            {
                "mes": mes,
                **r,
                "resultado": r["receita_recebida"]
                - r["custo_manutencao"]
                - r["custo_documentos"],
            }
        )
    return {"resultado": list(resultado.values()), "fluxo": meses}


def proporcoes(valores):
    """Largura (0 a 100) de cada barra proporcional, relativa ao maior valor.
    Valores negativos ou zerados ficam sem barra."""
    maior = max((v for v in valores), default=Decimal(0))
    if maior <= 0:
        return [0 for _ in valores]
    return [
        int((max(v, Decimal(0)) * 100 / maior).quantize(Decimal("1"), ROUND_HALF_UP))
        for v in valores
    ]


def agrupar_por_modelo(resultado):
    """Custo de manutenção por modelo: total e média por moto, do maior para o menor."""
    grupos = {}
    for r in resultado:
        grupo = grupos.setdefault(
            r["modelo"], {"modelo": r["modelo"], "motos": 0, "custo_total": Decimal(0)}
        )
        grupo["motos"] += 1
        grupo["custo_total"] += r["custo_manutencao"]
    linhas = []
    for g in grupos.values():
        g["custo_medio"] = (g["custo_total"] / g["motos"]).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        linhas.append(g)
    return sorted(linhas, key=lambda g: (-g["custo_total"], g["modelo"]))


def previsto_do_mes(cobrancas, hoje):
    """Carteira do mês: parcelas (sem caução, sem canceladas) que vencem no mês de `hoje`."""
    mes = hoje.isoformat()[:7]
    return sum(
        (
            valor(c["valor"])
            for c in cobrancas
            if str(c["vencimento"])[:7] == mes
            and c["tipo"] != "caucao"
            and c["situacao"] != "cancelada"
        ),
        Decimal(0),
    )


def analisar_inadimplencia(cobrancas, clientes, motos, config, hoje):
    """Posição atual das cobranças atrasadas: linhas (mais antigas primeiro), total
    em atraso, clientes distintos e % da carteira do mês (None sem carteira)."""
    nomes = {c["id"]: c["nome"] for c in clientes}
    placas = {m["id"]: m["placa"] for m in motos}
    linhas = []
    for c in cobrancas:
        if c["situacao"] != "atrasada":
            continue
        saldo = valor(c["saldo"])
        encargos = calcular_encargos(
            saldo,
            date.fromisoformat(str(c["vencimento"])[:10]),
            hoje,
            valor(config["multa_atraso_percentual"]),
            valor(config["juros_mensal_percentual"]),
            config["carencia_dias"],
        )
        linhas.append(
            {
                "cliente": nomes.get(c["cliente_id"], "Cliente"),
                "placa": placas.get(c["moto_id"], ""),
                "vencimento": c["vencimento"],
                "dias_atraso": max((hoje - date.fromisoformat(str(c["vencimento"])[:10])).days, 0),
                "saldo": saldo,
                "total_com_encargos": encargos["total"],
            }
        )
    linhas.sort(key=lambda l: (-l["dias_atraso"], l["cliente"]))
    total = sum((l["saldo"] for l in linhas), Decimal(0))
    previsto = previsto_do_mes(cobrancas, hoje)
    return {
        "linhas": linhas,
        "total_atraso": total,
        "clientes": len({c["cliente_id"] for c in cobrancas if c["situacao"] == "atrasada"}),
        "percentual_carteira": (
            (total * 100 / previsto).quantize(Decimal("0.1"), ROUND_HALF_UP)
            if previsto > 0
            else None
        ),
    }
