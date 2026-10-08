"""Contratos: lista, busca, paginação e ficha com abas remotas."""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain import contratos_lista
from src.domain.paginacao import OPCOES_POR_PAGINA
from src.web import dados_contratos
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _inteiro(valor, padrao):
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def _url_lista(status, busca, por_pagina, pagina=1):
    parametros = {}
    if status != contratos_lista.PADRAO:
        parametros["status"] = status
    if busca:
        parametros["q"] = busca
    if por_pagina != OPCOES_POR_PAGINA[0]:
        parametros["por_pagina"] = por_pagina
    if pagina > 1:
        parametros["pagina"] = pagina
    return "/contratos" + (f"?{urlencode(parametros)}" if parametros else "")


def _so_resultado(request):
    return (request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "resultado"
            and not request.headers.get("HX-History-Restore-Request"))


@router.get("/contratos")
def lista(request: Request, status: str | None = None, q: str | None = None, pagina: str | None = None,
          por_pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    status = contratos_lista.status_valido(status)
    busca = (q or "").strip()[:80]
    tamanho = _inteiro(por_pagina, OPCOES_POR_PAGINA[0])
    if tamanho not in OPCOES_POR_PAGINA:
        tamanho = OPCOES_POR_PAGINA[0]
    dados = dados_contratos.carregar_lista(status, busca, _inteiro(pagina, 1), tamanho)
    p = dados["pagina"]
    opcoes = ((contratos_lista.TODOS, "Todos"), *((x, contratos_lista.STATUS_ROTULO[x]) for x in contratos_lista.STATUS_ORDEM))
    contexto = {
        "titulo": "Contratos", "d": dados, "status": status, "busca": busca, "por_pagina": tamanho,
        "opcoes_por_pagina": OPCOES_POR_PAGINA, "status_rotulo": contratos_lista.STATUS_ROTULO,
        "periodos_rotulo": contratos_lista.PERIODOS_ROTULO,
        "chips": [(chave, rotulo, dados["total_cadastrados"] if chave == contratos_lista.TODOS else dados["contagem"][chave],
                   _url_lista(chave, busca, tamanho)) for chave, rotulo in opcoes],
        "url_anterior": _url_lista(status, busca, tamanho, p.pagina - 1) if p.tem_anterior else None,
        "url_proxima": _url_lista(status, busca, tamanho, p.pagina + 1) if p.tem_proxima else None,
        "url_limpar": _url_lista(contratos_lista.TODOS, "", tamanho),
        "filtrando": status != contratos_lista.PADRAO or bool(busca),
    }
    return renderizar(request, "contratos/_resultado.html" if _so_resultado(request) else "contratos/lista.html", contexto)


def _contrato_ou_404(contrato_id):
    try:
        UUID(contrato_id)
    except ValueError:
        raise HTTPException(status_code=404)
    registro = dados_contratos.obter_contrato(contrato_id)
    if registro is None:
        raise HTTPException(status_code=404)
    return registro


def _contexto_aba(registro, aba):
    contrato = registro["contrato"]
    base = f"/contratos/{contrato['id']}"
    return {**registro, "aba": aba, "status_rotulo": contratos_lista.STATUS_ROTULO,
            "periodos_rotulo": contratos_lista.PERIODOS_ROTULO,
            "abas_da_ficha": [(chave, rotulo, f"{base}/abas/{chave}", f"{base}?aba={chave}")
                              for chave, rotulo in contratos_lista.ABAS_FICHA],
            "a": dados_contratos.carregar_ficha(contrato, aba)}


@router.get("/contratos/{contrato_id}")
def ficha(request: Request, contrato_id: str, aba: str | None = None, _: Sessao = Depends(exigir_dono)):
    registro = _contrato_ou_404(contrato_id)
    contexto = _contexto_aba(registro, contratos_lista.aba_valida(aba))
    return renderizar(request, "contratos/ficha.html", {"titulo": registro["cliente"]["nome"], **contexto})


@router.get("/contratos/{contrato_id}/abas/{aba}")
def aba(request: Request, contrato_id: str, aba: str, _: Sessao = Depends(exigir_dono)):
    if aba not in dict(contratos_lista.ABAS_FICHA):
        raise HTTPException(status_code=404)
    return renderizar(request, "contratos/_resposta_aba.html", _contexto_aba(_contrato_ou_404(contrato_id), aba))
