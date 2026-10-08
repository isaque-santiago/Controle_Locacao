"""Cobranças: abas Hoje, Atrasadas, Próximos 7 dias e Pagas, com paginação."""

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


def _contexto(aba, pagina):
    dados = dados_cobrancas.carregar(aba, pagina)
    p = dados["pagina"]
    pagina_url = lambda n: f"/cobrancas?aba={aba}&pagina={n}"
    parcial_url = lambda n: f"/cobrancas/abas/{aba}?pagina={n}"
    return {
        "titulo": "Cobranças", "aba": aba, "d": dados, "formas_rotulo": cobrancas_lista.FORMAS_ROTULO,
        "vazio": cobrancas_lista.VAZIO[aba],
        "abas_da_lista": [
            (chave, f"{rotulo} · {dados['contagem'][chave]}", f"/cobrancas/abas/{chave}", f"/cobrancas?aba={chave}")
            for chave, rotulo in cobrancas_lista.ABAS
        ],
        "pag_anterior": pagina_url(p.pagina - 1) if p.tem_anterior else None,
        "pag_proxima": pagina_url(p.pagina + 1) if p.tem_proxima else None,
        "parcial_anterior": parcial_url(p.pagina - 1) if p.tem_anterior else None,
        "parcial_proxima": parcial_url(p.pagina + 1) if p.tem_proxima else None,
    }


@router.get("/cobrancas")
def lista(request: Request, aba: str | None = None, pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, "cobrancas/lista.html", _contexto(cobrancas_lista.aba_valida(aba), _inteiro(pagina, 1)))


@router.get("/cobrancas/abas/{aba}")
def painel_da_aba(request: Request, aba: str, pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    if aba not in dict(cobrancas_lista.ABAS):
        raise HTTPException(status_code=404)
    return renderizar(request, "cobrancas/_resposta_aba.html", _contexto(aba, _inteiro(pagina, 1)))
