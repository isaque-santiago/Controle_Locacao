"""Arquivos órfãos do portal: a lista vem da RPC `rpc_listar_arquivos_orfaos` e a remoção, da API do Storage.

A remoção usa a API (não um `delete` em `storage.objects`) porque só ela apaga também o arquivo, e não apenas a linha do banco.
O dono tem política de acesso total aos buckets `documentos` e `trocas_oleo` (migration 20260928120000)."""

from src.db import get_client


def listar(horas: int) -> list[dict]:
    """Arquivos sem nenhum registro e com mais de `horas` horas: [{bucket, caminho, tamanho, criado_em}]."""
    return get_client().rpc("rpc_listar_arquivos_orfaos", {"p_horas": horas}).execute().data or []


def remover(bucket: str, caminhos: list[str]) -> list[dict]:
    """Apaga os arquivos do bucket e devolve os que o Storage confirmou (cada um com `name`)."""
    return get_client().storage.from_(bucket).remove(caminhos) or []
