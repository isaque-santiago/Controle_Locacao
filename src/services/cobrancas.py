"""Orquestra geração de cobranças e registro de pagamentos."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.encargos import calcular_encargos
from src.repositories import cobrancas, configuracoes, pagamentos


def listar():
    return cobrancas.listar()


def listar_por_contrato(contrato_id: str):
    return cobrancas.listar_por_contrato(contrato_id)


def calcular_encargos_cobranca(cobranca: dict, data_referencia: date) -> dict:
    """Multa/juros de uma cobrança em aberto, para exibir na tela antes do pagamento."""
    config = configuracoes.obter()
    saldo = Decimal(str(cobranca["saldo"]))
    return calcular_encargos(
        saldo=saldo,
        vencimento=date.fromisoformat(cobranca["vencimento"]),
        data_referencia=data_referencia,
        multa_percentual=Decimal(str(config["multa_atraso_percentual"])),
        juros_mensal_percentual=Decimal(str(config["juros_mensal_percentual"])),
        carencia_dias=config["carencia_dias"],
    )


def registrar_pagamento(
    cobranca_id: str,
    data_pagamento: date,
    valor: Decimal,
    multa_juros: Decimal = Decimal("0"),
    forma: str = "pix",
    observacoes: Optional[str] = None,
) -> dict:
    if valor <= 0 or multa_juros < 0:
        raise ValueError(
            "O principal deve ser positivo e os encargos não podem ser negativos."
        )
    dados = {
        "cobranca_id": cobranca_id,
        "data_pagamento": data_pagamento.isoformat(),
        "valor": str(valor),
        "multa_juros": str(multa_juros),
        "forma": forma,
        "observacoes": observacoes,
    }
    return pagamentos.criar(dados)


def gerar_cobrancas_pendentes(horizonte_dias: int = 30) -> dict:
    return cobrancas.gerar_pendentes_via_rpc(horizonte_dias)


def historico_pagamentos(cobranca_id):
    return pagamentos.listar_por_cobranca(cobranca_id)


def historicos_pagamentos(cobranca_ids):
    """Agrupa em memória os pagamentos carregados em lote por cobrança."""
    ids = list(dict.fromkeys(cobranca_ids))
    historicos = {cobranca_id: [] for cobranca_id in ids}
    for pagamento in pagamentos.listar_por_cobrancas(ids):
        historicos.setdefault(pagamento["cobranca_id"], []).append(pagamento)
    return historicos
