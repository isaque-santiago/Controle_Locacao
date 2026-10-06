"""Motos: lista com filtro, busca e paginação (HTMX troca só o resultado)."""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain import motos_lista
from src.domain.paginacao import OPCOES_POR_PAGINA
from src.web import dados_motos
from src.web.apresentacao import formatar_placa
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


# ------------------------------------------------------------------ ficha --

def _moto_ou_404(moto_id: str) -> dict:
    try:
        UUID(moto_id)
    except ValueError:
        raise HTTPException(status_code=404)
    moto = dados_motos.obter_moto(moto_id)
    if moto is None:
        raise HTTPException(status_code=404)
    return moto


def _contexto_da_aba(moto: dict, aba: str) -> dict:
    return {
        "moto": moto,
        "aba": aba,
        "abas_da_ficha": [
            (chave, rotulo, f"/motos/{moto['id']}/abas/{chave}", f"/motos/{moto['id']}?aba={chave}")
            for chave, rotulo in motos_lista.ABAS_FICHA
        ],
        "status_rotulo": motos_lista.STATUS_ROTULO,
        "a": dados_motos.carregar_aba(moto, aba),
    }


@router.get("/motos/{moto_id}")
def ficha(
    request: Request,
    moto_id: str,
    aba: str | None = None,
    _: Sessao = Depends(exigir_dono),
):
    moto = _moto_ou_404(moto_id)
    contexto = _contexto_da_aba(moto, motos_lista.aba_valida(aba))
    contexto.update(
        titulo=f"Moto {formatar_placa(moto['placa'])}",
        cabecalho=dados_motos.carregar_cabecalho(moto),
    )
    return renderizar(request, "motos/ficha.html", contexto)


@router.get("/motos/{moto_id}/abas/{aba}")
def aba_da_ficha(
    request: Request,
    moto_id: str,
    aba: str,
    _: Sessao = Depends(exigir_dono),
):
    """Conteúdo de uma aba, para o HTMX trocar sem recarregar a página."""
    if aba not in {chave for chave, _rotulo in motos_lista.ABAS_FICHA}:
        raise HTTPException(status_code=404)
    moto = _moto_ou_404(moto_id)
    return renderizar(request, "motos/_painel.html", _contexto_da_aba(moto, aba))
