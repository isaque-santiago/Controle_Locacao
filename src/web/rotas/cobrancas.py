"""Cobranças: abas Hoje, Atrasadas, Próximos 7 dias e Pagas, com paginação."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain import cobrancas_lista
from src.web import dados_cobrancas
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _inteiro(valor, padrao):
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


_TAMANHO_MAXIMO_BUSCA = 80


def _consulta(busca, **extras):
    """Parâmetros da URL (`?aba=hoje&q=joana`): só o que foge do vazio; a ordem é a da chamada."""
    parametros = {chave: valor for chave, valor in extras.items() if valor}
    if busca:
        parametros["q"] = busca
    return urlencode(parametros)


def _busca(q):
    return " ".join((q or "").split())[:_TAMANHO_MAXIMO_BUSCA]


def _contexto(aba, pagina, busca=""):
    dados = dados_cobrancas.carregar(aba, pagina, busca)
    p = dados["pagina"]
    pagina_url = lambda n: "/cobrancas?" + _consulta(busca, aba=aba, pagina=n)
    parcial_url = lambda n: f"/cobrancas/abas/{aba}?" + _consulta(busca, pagina=n)
    return {
        "titulo": "Cobranças", "aba": aba, "d": dados, "formas_rotulo": cobrancas_lista.FORMAS_ROTULO, "busca": busca,
        "vazio": cobrancas_lista.VAZIO[aba],
        "abas_da_lista": [
            (chave, f"{rotulo} · {dados['contagem'][chave]}", f"/cobrancas/abas/{chave}" + (f"?{_consulta(busca)}" if busca else ""), "/cobrancas?" + _consulta(busca, aba=chave))
            for chave, rotulo in cobrancas_lista.ABAS
        ],
        "pag_anterior": pagina_url(p.pagina - 1) if p.tem_anterior else None,
        "pag_proxima": pagina_url(p.pagina + 1) if p.tem_proxima else None,
        "parcial_anterior": parcial_url(p.pagina - 1) if p.tem_anterior else None,
        "parcial_proxima": parcial_url(p.pagina + 1) if p.tem_proxima else None,
    }


@router.get("/cobrancas")
def lista(request: Request, aba: str | None = None, pagina: str | None = None, q: str | None = None, _: Sessao = Depends(exigir_dono)):
    """Página inteira; a busca instantânea (HTMX) pede o mesmo endereço e recebe só o painel da aba."""
    contexto = _contexto(cobrancas_lista.aba_valida(aba), _inteiro(pagina, 1), _busca(q))
    so_o_painel = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == "painel-aba"
        and not request.headers.get("HX-History-Restore-Request")
    )
    return renderizar(request, "cobrancas/_resposta_aba.html" if so_o_painel else "cobrancas/lista.html", contexto)


@router.get("/cobrancas/abas/{aba}")
def painel_da_aba(request: Request, aba: str, pagina: str | None = None, q: str | None = None, _: Sessao = Depends(exigir_dono)):
    if aba not in dict(cobrancas_lista.ABAS):
        raise HTTPException(status_code=404)
    return renderizar(request, "cobrancas/_resposta_aba.html", _contexto(aba, _inteiro(pagina, 1), _busca(q)))
