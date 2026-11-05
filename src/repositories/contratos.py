"""Leitura da tabela contratos e chamadas às RPCs de criação/encerramento.

Criação e encerramento de contrato sempre passam pela RPC (mexem em mais de
uma tabela numa transação só) — não existe inserção direta aqui.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

TABELA = "contratos"


@invalida_cache
def criar_com_vistoria(dados, vistoria, vistorias_vinculadas=None):
    parametros = {"payload": dados, "p_vistoria": vistoria}
    if vistorias_vinculadas:
        parametros["p_vistorias_vinculadas"] = vistorias_vinculadas
    return (
        get_client()
        .rpc("rpc_criar_contrato_com_vistoria", parametros)
        .execute()
        .data
    )


@invalida_cache
def encerrar_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao_danos, vistorias_vinculadas=None):
    parametros = {
        "p_contrato_id": contrato_id,
        "p_data": data.isoformat(),
        "p_vistoria": vistoria,
        "p_valor_danos": str(valor_danos),
        "p_descricao_danos": descricao_danos,
    }
    if vistorias_vinculadas:
        parametros["p_vistorias_vinculadas"] = vistorias_vinculadas
    return (
        get_client()
        .rpc("rpc_encerrar_contrato_com_vistoria", parametros)
        .execute()
        .data
    )


def listar():
    return todos(TABELA, ordem="criado_em")


def obter(contrato_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("id", contrato_id)
        .maybe_single()
        .execute()
    )
    return resposta.data if resposta else None


def listar_motos_do_contrato(contrato_id: str) -> list:
    """Motos do contrato (view `vw_contrato_motos`), a principal primeiro."""
    linhas = (
        get_client()
        .table("vw_contrato_motos")
        .select("*")
        .eq("contrato_id", contrato_id)
        .execute()
        .data
    )
    return sorted(linhas, key=lambda m: (not m["principal"], m["placa"]))


def listar_vinculos() -> list:
    """Linhas de `contrato_motos` (contrato_id, moto_id): as motos vinculadas de todos os contratos, numa consulta só.
    A tabela não tem `id`, por isso a ordem é pela chave composta."""
    return todos("contrato_motos", ordem=["contrato_id", "moto_id"])


def contar_vinculadas() -> dict:
    """Quantas motos vinculadas (além da principal) cada contrato tem: {contrato_id: n}, numa consulta só."""
    contagem: dict = {}
    for linha in listar_vinculos():
        contagem[linha["contrato_id"]] = contagem.get(linha["contrato_id"], 0) + 1
    return contagem


@invalida_cache
def atualizar(contrato_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", contrato_id).execute()
    return resposta.data[0]


@invalida_cache
def criar_via_rpc(payload: dict) -> dict:
    resposta = get_client().rpc("rpc_criar_contrato", {"payload": payload}).execute()
    return resposta.data


@invalida_cache
def encerrar_via_rpc(
    contrato_id: str,
    data: date,
    km_final: int,
    valor_danos: Decimal,
    descricao_danos: Optional[str],
) -> dict:
    resposta = (
        get_client()
        .rpc(
            "rpc_encerrar_contrato",
            {
                "p_contrato_id": contrato_id,
                "p_data": data.isoformat(),
                "p_km_final": km_final,
                "p_valor_danos": str(valor_danos),
                "p_descricao_danos": descricao_danos,
            },
        )
        .execute()
    )
    return resposta.data
