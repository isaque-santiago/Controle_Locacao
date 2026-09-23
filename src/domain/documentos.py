"""Regras puras de documentos da moto: situação de vencimento e sugestão do ano seguinte."""

from datetime import date
from typing import Optional

TIPOS_ANUAIS = ("ipva", "licenciamento", "seguro")


def situacao_documento(
    vencimento: date, regularizado: bool, hoje: date, alerta_dias: int
) -> str:
    """Situação de um documento — mesma regra da view vw_alertas_documentos:
    vencido (passou do vencimento), a_vencer (dentro do prazo de alerta) ou
    em_dia. Documento regularizado (pago/renovado) está sempre em dia."""
    if regularizado:
        return "em_dia"
    if vencimento < hoje:
        return "vencido"
    if (vencimento - hoje).days <= alerta_dias:
        return "a_vencer"
    return "em_dia"


def sugerir_proximo_documento(tipo: str, ano_referencia: Optional[int]) -> Optional[dict]:
    """Ao regularizar um documento de renovação anual (IPVA, licenciamento,
    seguro), sugere o cadastro do ano seguinte com vencimento em branco para
    o dono preencher. Para tipos sem renovação anual (vistoria_detran, outro)
    ou sem ano_referencia informado, não há sugestão."""
    if tipo not in TIPOS_ANUAIS or not ano_referencia:
        return None

    return {
        "tipo": tipo,
        "ano_referencia": ano_referencia + 1,
        "vencimento": None,
        "regularizado": False,
    }
