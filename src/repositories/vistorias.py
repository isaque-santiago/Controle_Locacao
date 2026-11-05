"""Leitura da tabela vistorias e chamada à RPC de registro.

Registrar vistoria sempre passa pela RPC (grava vistoria + histórico de km
numa transação só) — não existe inserção direta aqui.
"""

from src.db import get_client
from src.domain.vistorias_por_moto import da_moto
from src.repositories.consultas import invalida_cache

TABELA = "vistorias"


def listar():
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, fotos:vistoria_fotos(*)")
        .order("data", desc=True)
        .execute()
    )
    return resposta.data


_SELECT_COM_CONTRATO = "*, fotos:vistoria_fotos(*), contrato:contratos(moto_id)"


def listar_por_contrato(contrato_id: str, moto_id: str | None = None, todas: bool = False):
    """Vistorias do contrato. Por padrão, as da moto principal (as telas ainda mostram uma por contrato);
    `moto_id` pede as de uma moto e `todas=True` as de todas as motos do contrato."""
    resposta = (
        get_client()
        .table(TABELA)
        .select(_SELECT_COM_CONTRATO)
        .eq("contrato_id", contrato_id)
        .order("data")
        .execute()
    )
    return resposta.data if todas else da_moto(resposta.data, moto_id)


def obter(vistoria_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, fotos:vistoria_fotos(*)")
        .eq("id", vistoria_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


def obter_por_contrato_e_tipo(contrato_id: str, tipo: str, moto_id: str | None = None):
    """Vistoria do tipo no contrato, da moto principal (padrão) ou da `moto_id` pedida; None se não existir."""
    resposta = (
        get_client()
        .table(TABELA)
        .select(_SELECT_COM_CONTRATO)
        .eq("contrato_id", contrato_id)
        .eq("tipo", tipo)
        .execute()
    )
    return next(iter(da_moto(resposta.data, moto_id)), None)


@invalida_cache
def registrar_via_rpc(payload: dict) -> dict:
    resposta = get_client().rpc("rpc_registrar_vistoria", {"payload": payload}).execute()
    return resposta.data
