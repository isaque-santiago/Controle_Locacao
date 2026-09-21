"""Leitura das views de alerta (manutenção, documentos, CNH)."""

from src.db import get_client


def listar_manutencao():
    resposta = (
        get_client()
        .table("vw_alertas_manutencao")
        .select("*")
        .order("situacao")
        .execute()
    )
    return resposta.data


def listar_documentos():
    resposta = (
        get_client()
        .table("vw_alertas_documentos")
        .select("*")
        .order("vencimento")
        .execute()
    )
    return resposta.data


def listar_cnh():
    resposta = (
        get_client()
        .table("vw_alertas_cnh")
        .select("*")
        .order("cnh_validade")
        .execute()
    )
    return resposta.data
