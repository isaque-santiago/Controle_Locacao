"""Vistoria por moto em contrato com várias motos (entrega e devolução de cada moto).

A moto principal tem a vistoria de sempre; as vinculadas (`contrato_motos`) ganham a delas. O banco aceita
contrato sem a vistoria das vinculadas (contratos antigos); a tela é que exige (`exigir_todas_as_motos`).
Mesma regra das RPCs `rpc_criar_contrato_com_vistoria` e `rpc_encerrar_contrato_com_vistoria`.
"""

from typing import Iterable, Mapping, Optional

from src.domain.contrato_motos import todas_as_motos

TIPOS = ("entrega", "devolucao")


def validar_vistorias_vinculadas(
    moto_principal_id: str,
    vinculadas: Optional[Iterable[str]],
    vistorias: Optional[Iterable[dict]],
    km_atual_por_moto: Mapping[str, int],
) -> list:
    """Vistorias das vinculadas, validadas: cada uma de uma moto vinculada do contrato, sem repetir moto, com km
    inteiro e não menor que o `km_atual` da moto. Devolve a lista normalizada (vazia se não houver)."""
    ids_validos = set(todas_as_motos(moto_principal_id, vinculadas)[1:])
    vistas: set = set()
    normalizadas = []
    for v in vistorias or []:
        moto_id = str(v.get("moto_id") or "").strip()
        if not moto_id:
            raise ValueError("Informe a moto de cada vistoria.")
        if moto_id == str(moto_principal_id).strip():
            raise ValueError("A vistoria da moto principal vai em campo próprio, não na lista das vinculadas.")
        if moto_id not in ids_validos:
            raise ValueError("A vistoria é de uma moto que não pertence ao contrato.")
        if moto_id in vistas:
            raise ValueError("A mesma moto foi informada mais de uma vez.")
        vistas.add(moto_id)
        try:
            km = int(v.get("km"))
        except (TypeError, ValueError):
            raise ValueError("Informe a quilometragem de cada moto.") from None
        if km < 0:
            raise ValueError("A quilometragem não pode ser negativa.")
        if km < int(km_atual_por_moto.get(moto_id, 0)):
            raise ValueError("A quilometragem não pode ser menor que a atual da moto.")
        normalizadas.append({**v, "moto_id": moto_id, "km": km})
    return normalizadas


def da_moto(vistorias: Iterable[dict], moto_id: Optional[str] = None) -> list:
    """Vistorias de uma moto. Sem `moto_id`, as da moto principal do contrato (`contrato.moto_id`, trazido junto
    na consulta): as telas que ainda mostram uma vistoria por contrato seguem sem ver as das vinculadas."""
    if moto_id is not None:
        return [v for v in vistorias if v["moto_id"] == moto_id]
    return [v for v in vistorias if v["moto_id"] == (v.get("contrato") or {}).get("moto_id")]


def motos_sem_vistoria(
    moto_principal_id: str,
    vinculadas: Optional[Iterable[str]],
    vistorias_feitas: Iterable[dict],
    tipo: str,
) -> list:
    """Ids das motos do contrato (a principal primeiro) que ainda não têm a vistoria do `tipo`."""
    if tipo not in TIPOS:
        raise ValueError("tipo deve ser 'entrega' ou 'devolucao'.")
    feitas = {v["moto_id"] for v in vistorias_feitas if v["tipo"] == tipo}
    return [m for m in todas_as_motos(moto_principal_id, vinculadas) if m not in feitas]


def exigir_todas_as_motos(
    moto_principal_id: str,
    vinculadas: Optional[Iterable[str]],
    vistorias_vinculadas: Optional[Iterable[dict]],
) -> None:
    """Regra da tela: com vinculadas, todas precisam de vistoria. Levanta ValueError se faltar alguma."""
    esperadas = set(todas_as_motos(moto_principal_id, vinculadas)[1:])
    informadas = {str(v.get("moto_id") or "").strip() for v in vistorias_vinculadas or []}
    if esperadas - informadas:
        raise ValueError("Faça a vistoria de todas as motos do contrato.")
