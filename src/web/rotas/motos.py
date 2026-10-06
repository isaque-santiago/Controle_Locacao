"""Motos: lista com filtro, busca e paginação (HTMX troca só o resultado)."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request

from src.domain import motos_lista
from src.domain.paginacao import OPCOES_POR_PAGINA
from src.web import dados_motos
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

_TAMANHO_MAXIMO_BUSCA = 80


def _inteiro(valor: str | None, padrao: int) -> int:
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def _url_lista(situacao: str, busca: str, por_pagina: int, pagina: int = 1) -> str:
    """Endereço da lista só com o que foge do padrão (URL curta e fácil de compartilhar)."""
    parametros = {}
    if situacao != motos_lista.TODAS:
        parametros["situacao"] = situacao
    if busca:
        parametros["q"] = busca
    if por_pagina != OPCOES_POR_PAGINA[0]:
        parametros["por_pagina"] = por_pagina
    if pagina > 1:
        parametros["pagina"] = pagina
    return "/motos" + (f"?{urlencode(parametros)}" if parametros else "")


def _so_o_resultado(request: Request) -> bool:
    """Requisição HTMX que troca só #resultado (e não a restauração do histórico, que pede a página)."""
    cabecalhos = request.headers
    return (
        cabecalhos.get("HX-Request") == "true"
        and cabecalhos.get("HX-Target") == "resultado"
        and not cabecalhos.get("HX-History-Restore-Request")
    )


@router.get("/motos")
def lista(
    request: Request,
    situacao: str | None = None,
    q: str | None = None,
    pagina: str | None = None,
    por_pagina: str | None = None,
    _: Sessao = Depends(exigir_dono),
):
    situacao = motos_lista.situacao_valida(situacao)
    busca = (q or "").strip()[:_TAMANHO_MAXIMO_BUSCA]
    tamanho = _inteiro(por_pagina, OPCOES_POR_PAGINA[0])
    if tamanho not in OPCOES_POR_PAGINA:
        tamanho = OPCOES_POR_PAGINA[0]

    dados = dados_motos.carregar_lista(situacao, busca, _inteiro(pagina, 1), tamanho)
    p = dados["pagina"]
    contexto = {
        "titulo": "Motos",
        "d": dados,
        "situacao": situacao,
        "busca": busca,
        "por_pagina": tamanho,
        "opcoes_por_pagina": OPCOES_POR_PAGINA,
        "status_rotulo": motos_lista.STATUS_ROTULO,
        "chips": [
            (chave, rotulo, dados["contagem"][chave], _url_lista(chave, busca, tamanho))
            for chave, rotulo in (
                (motos_lista.TODAS, "Todas"),
                *((c, motos_lista.STATUS_ROTULO[c]) for c in motos_lista.STATUS_ORDEM),
            )
        ],
        "url_anterior": _url_lista(situacao, busca, tamanho, p.pagina - 1) if p.tem_anterior else None,
        "url_proxima": _url_lista(situacao, busca, tamanho, p.pagina + 1) if p.tem_proxima else None,
        "url_limpar": _url_lista(motos_lista.TODAS, "", tamanho),
        "filtrando": situacao != motos_lista.TODAS or bool(busca),
    }
    modelo = "motos/_resultado.html" if _so_o_resultado(request) else "motos/lista.html"
    return renderizar(request, modelo, contexto)
