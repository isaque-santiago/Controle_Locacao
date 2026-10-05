"""Orquestra geração de cobranças e registro de pagamentos."""

from datetime import date
from decimal import Decimal
from time import monotonic
from typing import Optional

import streamlit as st

from src.domain.encargos import calcular_encargos
from src.repositories import cobrancas, configuracoes, pagamentos

_CHAVE_GERACAO = "cobrancas_geradas_em"
_INTERVALO_GERACAO_SEGUNDOS = 3600


def listar():
    return cobrancas.listar()


def configuracao_encargos() -> dict:
    return configuracoes.obter()


def listar_por_contrato(contrato_id: str):
    return cobrancas.listar_por_contrato(contrato_id)


def calcular_encargos_cobranca(
    cobranca: dict, data_referencia: date, config: Optional[dict] = None
) -> dict:
    """Encargos fixos (multa + adicional diário) de uma cobrança em aberto, para exibir na tela
    antes do pagamento. Só cobranças de locação têm encargos.

    Passe `config` para calcular várias cobranças sem reler as configurações."""
    config = config or configuracoes.obter()
    return calcular_encargos(
        tipo=cobranca["tipo"],
        saldo=Decimal(str(cobranca["saldo"])),
        vencimento=date.fromisoformat(cobranca["vencimento"]),
        data_referencia=data_referencia,
        multa_valor=Decimal(str(config["multa_atraso_valor"])),
        adicional_diario_valor=Decimal(str(config["encargo_diario_valor"])),
    )


def registrar_pagamento(
    cobranca_id: str,
    data_pagamento: date,
    valor: Decimal,
    multa_juros: Decimal = Decimal("0"),
    forma: str = "pix",
    observacoes: Optional[str] = None,
    chave_operacao: Optional[str] = None,
) -> dict:
    """Registra o pagamento. `chave_operacao` torna o reenvio idempotente: repetir o mesmo envio
    devolve o pagamento já gravado em vez de lançar outro."""
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
    return pagamentos.criar(dados, chave_operacao)


def gerar_cobrancas_pendentes(horizonte_dias: int = 30) -> dict:
    """Gera as cobranças pendentes, no máximo uma vez por hora em cada sessão.

    A RPC é idempotente e só atua em contratos sem prazo (exceção neste sistema);
    rodá-la a cada abertura do Dashboard era uma escrita a mais no banco por página."""
    agora = monotonic()
    ultima = st.session_state.get(_CHAVE_GERACAO)
    if ultima is not None and agora - ultima < _INTERVALO_GERACAO_SEGUNDOS:
        return {"cobrancas_geradas": 0}
    resultado = cobrancas.gerar_pendentes_via_rpc(horizonte_dias)
    st.session_state[_CHAVE_GERACAO] = agora
    return resultado


def historico_pagamentos(cobranca_id):
    return pagamentos.listar_por_cobranca(cobranca_id)


def historicos_pagamentos(cobranca_ids):
    """Agrupa em memória os pagamentos carregados em lote por cobrança."""
    ids = list(dict.fromkeys(cobranca_ids))
    historicos = {cobranca_id: [] for cobranca_id in ids}
    for pagamento in pagamentos.listar_por_cobrancas(ids):
        historicos.setdefault(pagamento["cobranca_id"], []).append(pagamento)
    return historicos
