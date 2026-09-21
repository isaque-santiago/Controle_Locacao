"""Indicadores mensais e lista de maiores devedores."""

from collections import defaultdict
from decimal import Decimal
from src.domain.valores import hoje_br
from src.domain.relatorios import valor
from src.services import relatorios, motos, cobrancas, clientes


def resumo():
    hoje = hoje_br()
    frota = motos.listar()
    parcelas = cobrancas.listar()
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    mensal = relatorios.resultado_por_moto(hoje.replace(day=1), hoje)["resultado"]
    devedores = defaultdict(lambda: Decimal(0))
    for c in parcelas:
        if c["situacao"] == "atrasada":
            devedores[c["cliente_id"]] += valor(c["saldo"])
    return {
        "frota": frota,
        "cobrancas": parcelas,
        "recebido": sum((r["receita_recebida"] for r in mensal), Decimal(0)),
        "manutencao": sum((r["custo_manutencao"] for r in mensal), Decimal(0)),
        "previsto": sum(
            (
                valor(c["valor"])
                for c in parcelas
                if c["vencimento"][:7] == hoje.isoformat()[:7]
                and c["tipo"] != "caucao"
                and c["situacao"] != "cancelada"
            ),
            Decimal(0),
        ),
        "atrasado": sum(devedores.values(), Decimal(0)),
        "devedores": [
            {"cliente": nomes.get(id, "Cliente"), "saldo": saldo}
            for id, saldo in sorted(
                devedores.items(), key=lambda par: par[1], reverse=True
            )
        ],
    }
