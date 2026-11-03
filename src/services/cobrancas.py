"""Orquestra geração de cobranças e registro de pagamentos."""

from datetime import date
from decimal import Decimal
from threading import Lock
from time import monotonic
from typing import Optional

from src.db import usuario_id_atual
from src.domain.encargos import calcular_encargos
from src.repositories import cobrancas, configuracoes, pagamentos

_INTERVALO_GERACAO_SEGUNDOS = 3600
# Última geração por usuário (vale para o Streamlit e para o app web).
_ULTIMA_GERACAO: dict[str | None, float] = {}
_TRAVA_GERACAO = Lock()


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
    """Gera as cobranças pendentes, no máximo uma vez por hora para cada usuário.

    A RPC é idempotente e atua nos contratos ativos por prazo indeterminado (a regra da
    operação), gerando as cobranças da janela móvel; rodá-la a cada abertura do Dashboard
    era uma escrita a mais no banco por página."""
    agora = monotonic()
    usuario = usuario_id_atual()
    with _TRAVA_GERACAO:
        ultima = _ULTIMA_GERACAO.get(usuario)
        if ultima is not None and agora - ultima < _INTERVALO_GERACAO_SEGUNDOS:
            return {"cobrancas_geradas": 0}
        # Marca antes de chamar: requisições simultâneas não disparam a RPC duas vezes.
        _ULTIMA_GERACAO[usuario] = agora
    try:
        return cobrancas.gerar_pendentes_via_rpc(horizonte_dias)
    except Exception:
        with _TRAVA_GERACAO:
            _ULTIMA_GERACAO.pop(usuario, None)
        raise


def historico_pagamentos(cobranca_id):
    return pagamentos.listar_por_cobranca(cobranca_id)


def historicos_pagamentos(cobranca_ids):
    """Agrupa em memória os pagamentos carregados em lote por cobrança."""
    ids = list(dict.fromkeys(cobranca_ids))
    historicos = {cobranca_id: [] for cobranca_id in ids}
    for pagamento in pagamentos.listar_por_cobrancas(ids):
        historicos.setdefault(pagamento["cobranca_id"], []).append(pagamento)
    return historicos
