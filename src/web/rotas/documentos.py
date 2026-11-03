"""Documentos da frota: lista com filtro por situação, busca por placa e paginação, e abertura do comprovante."""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from src.domain import documentos_lista
from src.domain.paginacao import OPCOES_POR_PAGINA
from src.web import dados_documentos
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _inteiro(valor, padrao):
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def _url_lista(situacao, busca, por_pagina, pagina=1):
    parametros = {}
    if situacao != documentos_lista.TODOS:
        parametros["situacao"] = situacao
    if busca:
        parametros["q"] = busca
    if por_pagina != OPCOES_POR_PAGINA[0]:
        parametros["por_pagina"] = por_pagina
    if pagina > 1:
        parametros["pagina"] = pagina
    return "/documentos" + (f"?{urlencode(parametros)}" if parametros else "")


def _so_resultado(request):
    return (request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "resultado"
            and not request.headers.get("HX-History-Restore-Request"))


@router.get("/documentos")
def lista(request: Request, situacao: str | None = None, q: str | None = None, pagina: str | None = None,
          por_pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    situacao = documentos_lista.situacao_valida(situacao)
    busca = (q or "").strip()[:80]
    tamanho = _inteiro(por_pagina, OPCOES_POR_PAGINA[0])
    if tamanho not in OPCOES_POR_PAGINA:
        tamanho = OPCOES_POR_PAGINA[0]
    dados = dados_documentos.carregar_lista(situacao, busca, _inteiro(pagina, 1), tamanho)
    p = dados["pagina"]
    opcoes = ((documentos_lista.TODOS, "Todos"), *((s, documentos_lista.SITUACAO_ROTULO[s]) for s in documentos_lista.SITUACOES_ORDEM))
    contexto = {
        "titulo": "Documentos", "d": dados, "situacao": situacao, "busca": busca, "por_pagina": tamanho,
        "opcoes_por_pagina": OPCOES_POR_PAGINA, "tipos": documentos_lista.TIPOS_ROTULO,
        "tom": documentos_lista.TOM_SITUACAO, "vencidos": dados["contagem"]["vencido"], "a_vencer": dados["contagem"]["a_vencer"],
        "chips": [(chave, rotulo, dados["contagem"][chave], _url_lista(chave, busca, tamanho)) for chave, rotulo in opcoes],
        "url_anterior": _url_lista(situacao, busca, tamanho, p.pagina - 1) if p.tem_anterior else None,
        "url_proxima": _url_lista(situacao, busca, tamanho, p.pagina + 1) if p.tem_proxima else None,
        "url_limpar": _url_lista(documentos_lista.TODOS, "", tamanho),
        "filtrando": situacao != documentos_lista.TODOS or bool(busca),
    }
    return renderizar(request, "documentos/_resultado.html" if _so_resultado(request) else "documentos/lista.html", contexto)


@router.get("/documentos/{documento_id}/comprovante")
async def comprovante(documento_id: str, _: Sessao = Depends(exigir_dono)):
    """Assina o link na hora do clique (vale 5 minutos) e leva o navegador até o arquivo."""
    try:
        UUID(documento_id)
    except ValueError:
        raise HTTPException(status_code=404)
    url = await run_in_threadpool(dados_documentos.url_comprovante, documento_id)
    if not url:
        raise HTTPException(status_code=404)
    return RedirectResponse(url, status_code=303)
