"""Regra pura de documentos da moto: sugestão do documento do ano seguinte."""

from typing import Optional

TIPOS_ANUAIS = ("ipva", "licenciamento", "seguro")


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
