"""Orquestra registro de vistorias, fotos e comparação entrega x devolução."""

from datetime import datetime
from typing import Optional

from postgrest.exceptions import APIError

from src.domain.vistorias import checklist_inicial, comparar_checklists
from src.repositories import vistoria_fotos, vistorias

_CODIGO_VIOLACAO_UNICIDADE = "23505"


def listar_por_contrato(contrato_id: str):
    return vistorias.listar_por_contrato(contrato_id)


def obter(vistoria_id: str):
    return vistorias.obter(vistoria_id)


def checklist_padrao() -> dict:
    return checklist_inicial()


def registrar_vistoria(
    contrato_id: str,
    moto_id: str,
    tipo: str,
    km: int,
    checklist: dict,
    data: Optional[datetime] = None,
    nivel_combustivel: Optional[str] = None,
    avarias: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Registra a vistoria (entrega ou devolução) e grava o km no histórico,
    via RPC. Uma vistoria de cada tipo por contrato (índice único no banco)."""
    if tipo not in ("entrega", "devolucao"):
        raise ValueError("tipo deve ser 'entrega' ou 'devolucao'.")

    payload = {
        "contrato_id": contrato_id,
        "moto_id": moto_id,
        "tipo": tipo,
        "data": data.isoformat() if data else None,
        "km": km,
        "nivel_combustivel": nivel_combustivel,
        "checklist": checklist,
        "avarias": avarias,
        "observacoes": observacoes,
    }
    try:
        return vistorias.registrar_via_rpc(payload)
    except APIError as erro:
        if erro.code == _CODIGO_VIOLACAO_UNICIDADE:
            raise ValueError(
                f"Já existe uma vistoria de '{tipo}' para este contrato."
            ) from erro
        raise


def anexar_foto(
    vistoria_id: str,
    nome_arquivo: str,
    conteudo: bytes,
    content_type: str,
    legenda: Optional[str] = None,
) -> dict:
    caminho = vistoria_fotos.upload_foto(vistoria_id, nome_arquivo, conteudo, content_type)
    return vistoria_fotos.criar(
        {"vistoria_id": vistoria_id, "storage_path": caminho, "legenda": legenda}
    )


def url_foto(storage_path: str, expira_em: int = 300) -> str:
    """URL assinada de curta duração — o bucket 'vistorias' é privado."""
    return vistoria_fotos.url_assinada(storage_path, expira_em)


def comparar_entrega_devolucao(contrato_id: str) -> dict:
    """Compara os checklists de entrega e devolução do contrato lado a lado;
    diferencas fica None enquanto algum dos dois ainda não foi registrado."""
    entrega = vistorias.obter_por_contrato_e_tipo(contrato_id, "entrega")
    devolucao = vistorias.obter_por_contrato_e_tipo(contrato_id, "devolucao")

    diferencas = None
    if entrega is not None and devolucao is not None:
        diferencas = comparar_checklists(entrega["checklist"], devolucao["checklist"])

    return {"entrega": entrega, "devolucao": devolucao, "diferencas": diferencas}
