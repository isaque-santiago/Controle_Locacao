"""Vistorias: lista com filtro por tipo, busca e paginação, e comparação entrega x devolução (somente leitura)."""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain import vistorias_lista
from src.domain.paginacao import OPCOES_POR_PAGINA
from src.web import dados_vistorias
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _inteiro(valor, padrao):
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def _url_lista(tipo, busca, por_pagina, pagina=1):
    parametros = {}
    if tipo != vistorias_lista.TODAS:
        parametros["tipo"] = tipo
    if busca:
        parametros["q"] = busca
    if por_pagina != OPCOES_POR_PAGINA[0]:
        parametros["por_pagina"] = por_pagina
    if pagina > 1:
        parametros["pagina"] = pagina
    return "/vistorias" + (f"?{urlencode(parametros)}" if parametros else "")


def _so_resultado(request):
    return (request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "resultado"
            and not request.headers.get("HX-History-Restore-Request"))


@router.get("/vistorias")
def lista(request: Request, tipo: str | None = None, q: str | None = None, pagina: str | None = None,
          por_pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    tipo = vistorias_lista.tipo_valido(tipo)
    busca = (q or "").strip()[:80]
    tamanho = _inteiro(por_pagina, OPCOES_POR_PAGINA[0])
    if tamanho not in OPCOES_POR_PAGINA:
        tamanho = OPCOES_POR_PAGINA[0]
    dados = dados_vistorias.carregar_lista(tipo, busca, _inteiro(pagina, 1), tamanho)
    p = dados["pagina"]
    opcoes = ((vistorias_lista.TODAS, "Todas"), *((t, vistorias_lista.TIPO_ROTULO[t]) for t in vistorias_lista.TIPOS_ORDEM))
    contexto = {
        "titulo": "Vistorias", "d": dados, "tipo": tipo, "busca": busca, "por_pagina": tamanho,
        "opcoes_por_pagina": OPCOES_POR_PAGINA, "tipo_rotulo": vistorias_lista.TIPO_ROTULO,
        "chips": [(chave, rotulo, dados["contagem"][chave], _url_lista(chave, busca, tamanho)) for chave, rotulo in opcoes],
        "url_anterior": _url_lista(tipo, busca, tamanho, p.pagina - 1) if p.tem_anterior else None,
        "url_proxima": _url_lista(tipo, busca, tamanho, p.pagina + 1) if p.tem_proxima else None,
        "url_limpar": _url_lista(vistorias_lista.TODAS, "", tamanho),
        "filtrando": tipo != vistorias_lista.TODAS or bool(busca),
    }
    return renderizar(request, "vistorias/_resultado.html" if _so_resultado(request) else "vistorias/lista.html", contexto)


@router.get("/vistorias/contrato/{contrato_id}")
def comparacao(request: Request, contrato_id: str, _: Sessao = Depends(exigir_dono)):
    try:
        UUID(contrato_id)
    except ValueError:
        raise HTTPException(status_code=404)
    dados = dados_vistorias.obter_comparacao(contrato_id)
    if dados is None:
        raise HTTPException(status_code=404)
    return renderizar(request, "vistorias/comparacao.html", {
        "titulo": "Vistorias de " + dados["cliente"]["nome"], "c": dados, "estado_item": vistorias_lista.ESTADO_ITEM,
    })
