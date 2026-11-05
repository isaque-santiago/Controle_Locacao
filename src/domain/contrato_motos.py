"""Contrato com mais de uma moto (ex.: Plano Conquista, uma parcela única que vale por duas motos).

A moto PRINCIPAL é a de `contratos.moto_id`: a parcela, a receita e os relatórios por veículo ficam nela.
As demais são "vinculadas" (`contrato_motos`) e só ocupam a moto enquanto o contrato estiver ativo.
Mesma regra da RPC `rpc_criar_contrato`.
"""

from typing import Iterable, Optional

MAX_MOTOS_POR_CONTRATO = 5


def normalizar_motos_vinculadas(moto_principal_id: str, vinculadas: Optional[Iterable[str]]) -> list:
    """Ids das motos vinculadas, sem vazios, validados: sem repetição, sem a principal e no máximo
    `MAX_MOTOS_POR_CONTRATO` motos no contrato (contando a principal). Devolve lista vazia se não houver."""
    ids = [str(v).strip() for v in (vinculadas or []) if v is not None and str(v).strip()]
    principal = str(moto_principal_id).strip()
    if len(set(ids)) != len(ids):
        raise ValueError("A mesma moto foi informada mais de uma vez.")
    if principal in ids:
        raise ValueError("A moto principal não pode estar na lista de motos vinculadas.")
    if len(ids) + 1 > MAX_MOTOS_POR_CONTRATO:
        raise ValueError(f"Um contrato aceita até {MAX_MOTOS_POR_CONTRATO} motos.")
    return ids


def todas_as_motos(moto_principal_id: str, vinculadas: Optional[Iterable[str]]) -> list:
    """Todas as motos do contrato, a principal primeiro."""
    return [str(moto_principal_id).strip(), *normalizar_motos_vinculadas(moto_principal_id, vinculadas)]


def contratos_por_moto(contratos: Iterable[dict], vinculos: Iterable[dict]) -> dict:
    """{moto_id: contrato ativo}, contando a moto principal (`contratos.moto_id`) e as vinculadas
    (`vinculos` = linhas de `contrato_motos` com `contrato_id` e `moto_id`). Se a mesma moto aparecer em
    mais de um contrato ativo, a principal vale mais que a vinculada."""
    ativos = {c["id"]: c for c in contratos if c["status"] == "ativo"}
    mapa: dict = {}
    for v in vinculos:
        contrato = ativos.get(v["contrato_id"])
        if contrato:
            mapa[v["moto_id"]] = contrato
    for contrato in ativos.values():
        mapa[contrato["moto_id"]] = contrato
    return mapa


def contratos_da_moto(moto_id: str, contratos: Iterable[dict], vinculos: Iterable[dict]) -> list:
    """Todos os contratos (de qualquer situação) em que a moto entra, como principal ou vinculada."""
    ids_vinculados = {v["contrato_id"] for v in vinculos if v["moto_id"] == moto_id}
    return [c for c in contratos if c["moto_id"] == moto_id or c["id"] in ids_vinculados]
