"""Limpeza dos arquivos órfãos do portal (botão em Configurações): procurar, mostrar e apagar depois da confirmação do dono."""

import logging

from postgrest.exceptions import APIError

from src.domain.arquivos_orfaos import HORAS_MINIMAS, agrupar_por_bucket, em_lotes, formatar_tamanho, resumir
from src.repositories import arquivos_orfaos

log = logging.getLogger(__name__)

_CODIGO_REGRA_DE_NEGOCIO = "P0001"  # raise exception ... nas RPCs


def _listar(horas: int) -> list[dict]:
    try:
        return arquivos_orfaos.listar(horas)
    except APIError as erro:
        if erro.code == _CODIGO_REGRA_DE_NEGOCIO:
            raise ValueError(erro.message) from erro
        raise


def procurar(horas: int = HORAS_MINIMAS) -> dict:
    """Resumo dos arquivos órfãos (quantidade, tamanho, por bucket e a lista) para o dono conferir antes de apagar."""
    return resumir(_listar(horas))


def apagar(horas: int = HORAS_MINIMAS) -> dict:
    """Apaga os arquivos órfãos. A lista é calculada DE NOVO aqui, nunca vem do navegador, então só o que o banco aponta como órfão
    (e velho o bastante) é removido. Uma falha em um lote não impede os outros: devolve {apagados, tamanho, falhas}."""
    arquivos = _listar(horas)
    tamanhos = {(a["bucket"], a["caminho"]): int(a.get("tamanho") or 0) for a in arquivos}
    apagados = falhas = bytes_apagados = 0
    for bucket, caminhos in agrupar_por_bucket(arquivos).items():
        for lote in em_lotes(caminhos):
            try:
                removidos = arquivos_orfaos.remover(bucket, lote)
            except Exception:
                log.exception("Não foi possível apagar um lote de %s arquivo(s) órfão(s) do bucket %s.", len(lote), bucket)
                falhas += len(lote)
                continue
            if len(removidos) >= len(lote):
                confirmados = lote
            else:
                nomes = {r.get("name") for r in removidos}
                confirmados = [c for c in lote if c in nomes]
            apagados += len(confirmados)
            falhas += len(lote) - len(confirmados)
            bytes_apagados += sum(tamanhos[(bucket, c)] for c in confirmados)
    return {"apagados": apagados, "tamanho": formatar_tamanho(bytes_apagados), "falhas": falhas}
