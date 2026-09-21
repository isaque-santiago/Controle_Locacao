"""Consolida finanças com Decimal, sem duplicar receitas por junções."""

from collections import defaultdict
from decimal import Decimal


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
