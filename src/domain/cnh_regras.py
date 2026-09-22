"""Situação da CNH do cliente (em_dia, a_vencer, vencida).

Mesma regra da view vw_alertas_cnh, replicada aqui para ser usada na ficha e
na lista de clientes sem depender de haver um contrato ativo (a view só
alerta clientes com contrato ativo; a tela mostra a validade para todos)."""

from datetime import date
from typing import Optional


def situacao_cnh(validade: Optional[date], hoje: date, alerta_dias: int) -> str:
    if validade is None:
        return "sem_cnh"
    if validade < hoje:
        return "vencida"
    if (validade - hoje).days <= alerta_dias:
        return "a_vencer"
    return "em_dia"
