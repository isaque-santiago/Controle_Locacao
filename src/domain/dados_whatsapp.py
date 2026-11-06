"""Converte a leitura de `rpc_whatsapp_dados` (JSON: datas e valores em texto) nos tipos que as regras usam.

Dinheiro vira `Decimal` e datas viram `date`. Nenhum acesso ao banco aqui.
"""

from datetime import date
from decimal import Decimal

from src.domain.avisos_whatsapp import ConfigAvisos


def _data(valor):
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _dinheiro(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else "0"))


def config_do_envio(bruto: dict) -> dict:
    """Controles de Configurações: `ativo`, `modo_teste`, `numero_teste` e o `ConfigAvisos` das regras."""
    c = bruto["config"]
    return {
        "ativo": bool(c.get("ativo")),
        "modo_teste": c.get("modo_teste", True) is not False,  # na dúvida, modo teste
        "numero_teste": c.get("numero_teste") or None,
        "avisos": ConfigAvisos(
            max_repeticoes=int(c["max_repeticoes"]), dias_inadimplencia=int(c["dias_inadimplencia"]),
            multa_atraso=_dinheiro(c["multa_atraso"]), encargo_diario=_dinheiro(c["encargo_diario"]),
        ),
    }


def entradas_das_regras(bruto: dict) -> dict:
    """Argumentos de `avisos_devidos` (menos `dia_envio`) a partir da leitura."""
    historico: dict = {}
    for item in bruto.get("historico", []):
        historico.setdefault((item["tipo"], str(item["referencia_id"])), []).append(_data(item["data_referencia"]))

    return {
        "cobrancas": [dict(c, vencimento=_data(c["vencimento"]), saldo=_dinheiro(c["saldo"])) for c in bruto["cobrancas"]],
        "pagamentos": [dict(p, data_pagamento=_data(p["data_pagamento"]), vencimento=_data(p["vencimento"]),
                            valor=_dinheiro(p["valor"]), saldo_restante=_dinheiro(p["saldo_restante"]))
                       for p in bruto["pagamentos"]],
        "cnhs": [dict(c, cnh_validade=_data(c["cnh_validade"])) for c in bruto["cnhs"]],
        "documentos": [dict(d, vencimento=_data(d["vencimento"])) for d in bruto["documentos"]],
        "oleo": [dict(o, ultima_data=_data(o.get("ultima_data"))) for o in bruto["oleo"]],
        "portal": [dict(e, ocorrido_em=_data(e["ocorrido_em"])) for e in bruto["portal"]],
        "historico": historico,
    }


def clientes_da_leitura(bruto: dict) -> dict:
    """`{cliente_id: {"nome", "whatsapp"}}` para montar as mensagens."""
    return {c["id"]: {"nome": c["nome"], "whatsapp": c.get("whatsapp")} for c in bruto["clientes"]}
