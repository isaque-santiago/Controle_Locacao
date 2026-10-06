"""Clientes: lista, busca, paginação e ficha com abas remotas."""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain import clientes_lista
from src.domain.paginacao import OPCOES_POR_PAGINA
from src.web import dados_clientes
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
    if status != clientes_lista.TODOS:
        parametros["status"] = status
    if busca:
        parametros["q"] = busca
    if por_pagina != OPCOES_POR_PAGINA[0]:
        parametros["por_pagina"] = por_pagina
    if pagina > 1:
        parametros["pagina"] = pagina
    return "/clientes" + (f"?{urlencode(parametros)}" if parametros else "")


def _so_resultado(request):
    return request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "resultado" and not request.headers.get("HX-History-Restore-Request")


@router.get("/clientes")
def lista(request: Request, status: str | None = None, q: str | None = None, pagina: str | None = None,
          por_pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    status = clientes_lista.status_valido(status)
    busca = (q or "").strip()[:80]
    tamanho = _inteiro(por_pagina, OPCOES_POR_PAGINA[0])
    if tamanho not in OPCOES_POR_PAGINA:
        tamanho = OPCOES_POR_PAGINA[0]
    dados = dados_clientes.carregar_lista(status, busca, _inteiro(pagina, 1), tamanho)
    p = dados["pagina"]
    contexto = {
        "titulo": "Clientes", "d": dados, "status": status, "busca": busca, "por_pagina": tamanho,
        "opcoes_por_pagina": OPCOES_POR_PAGINA, "status_rotulo": clientes_lista.STATUS_ROTULO,
        "chips": [(chave, rotulo, dados["total_cadastrados"] if chave == clientes_lista.TODOS else dados["contagem"][chave], _url_lista(chave, busca, tamanho))
                  for chave, rotulo in ((clientes_lista.TODOS, "Todos"), *((x, clientes_lista.STATUS_ROTULO[x]) for x in clientes_lista.STATUS_ORDEM))],
        "url_anterior": _url_lista(status, busca, tamanho, p.pagina - 1) if p.tem_anterior else None,
        "url_proxima": _url_lista(status, busca, tamanho, p.pagina + 1) if p.tem_proxima else None,
        "url_limpar": _url_lista(clientes_lista.TODOS, "", tamanho), "filtrando": status != clientes_lista.TODOS or bool(busca),
    }
    return renderizar(request, "clientes/_resultado.html" if _so_resultado(request) else "clientes/lista.html", contexto)


def _cliente_ou_404(cliente_id):
    try:
        UUID(cliente_id)
    except ValueError:
        raise HTTPException(status_code=404)
    cliente = dados_clientes.obter_cliente(cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404)
    return cliente


def _contexto_aba(cliente, aba):
    return {"cliente": cliente, "aba": aba, "status_rotulo": clientes_lista.STATUS_ROTULO,
            "abas_da_ficha": [(chave, rotulo, f"/clientes/{cliente['id']}/abas/{chave}", f"/clientes/{cliente['id']}?aba={chave}") for chave, rotulo in clientes_lista.ABAS_FICHA],
            "a": dados_clientes.carregar_ficha(cliente, aba)}


@router.get("/clientes/{cliente_id}")
def ficha(request: Request, cliente_id: str, aba: str | None = None, _: Sessao = Depends(exigir_dono)):
    cliente = _cliente_ou_404(cliente_id)
    return renderizar(request, "clientes/ficha.html", {"titulo": cliente["nome"], **_contexto_aba(cliente, clientes_lista.aba_valida(aba))})


@router.get("/clientes/{cliente_id}/abas/{aba}")
def aba(request: Request, cliente_id: str, aba: str, _: Sessao = Depends(exigir_dono)):
    if aba not in dict(clientes_lista.ABAS_FICHA):
        raise HTTPException(status_code=404)
    return renderizar(request, "clientes/_resposta_aba.html", _contexto_aba(_cliente_ou_404(cliente_id), aba))
