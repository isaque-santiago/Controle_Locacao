"""Conclusão e cancelamento de manutenções abertas."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import formulario_manutencao as formulario, mensagens
from src.domain.valores import hoje_br
from src.web import acoes_manutencao, dados_manutencao
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()
ACOES = {"concluir": "concluida", "cancelar": "cancelada"}


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _aberta_ou_404(manutencao_id):
    registro = dados_manutencao.obter_aberta(manutencao_id)
    if registro is None:
        raise HTTPException(status_code=404)
    return registro


def _contexto(registro, acao, valores, erros=None, erro_geral=None):
    m, moto = registro["manutencao"], registro["moto"]
    return {
        **registro, "titulo": "Concluir manutenção" if acao == "concluir" else "Cancelar manutenção",
        "acao_nome": acao, "status_destino": ACOES[acao], "acao": f"/manutencao/{m['id']}/{acao}",
        "v": valores, "erros": erros or {}, "erro_geral": erro_geral,
        "km_minimo": max(int(moto["km_atual"]), int(m["km"])),
    }


@router.get("/manutencao/{manutencao_id}/{acao}")
def abrir(request: Request, manutencao_id: str, acao: str, _: Sessao = Depends(exigir_dono)):
    if acao not in ACOES:
        raise HTTPException(status_code=404)
    registro = _aberta_ou_404(manutencao_id)
    valores = formulario.valores_finalizacao(hoje_br(), registro["manutencao"], registro["moto"])
    modelo = "manutencao/_form_finalizacao.html" if _htmx(request) else "manutencao/finalizacao.html"
    return renderizar(request, modelo, _contexto(registro, acao, valores))


def _finalizar(request, sessao, manutencao_id, acao, entrada):
    if acao not in ACOES:
        raise HTTPException(status_code=404)
    registro = _aberta_ou_404(manutencao_id)
    valores = {**entrada, "confirmar": bool(entrada.get("confirmar"))}
    contexto = _contexto(registro, acao, valores)

    def gravar():
        dados = formulario.ler_finalizacao(valores, registro["manutencao"], registro["moto"], ACOES[acao])
        acoes_manutencao.finalizar(manutencao_id, dados["status"], dados["data"], dados["km"])
        aviso = mensagens.manutencao_finalizada(formatar_placa(registro["moto"]["placa"]), acao == "concluir")
        return _concluir(request, sessao, "/manutencao?aba=historico", aviso)

    modelo = "manutencao/_form_finalizacao.html" if _htmx(request) else "manutencao/finalizacao.html"
    return _devolver_formulario(request, modelo, contexto, gravar)


@router.post("/manutencao/{manutencao_id}/{acao}", dependencies=[Depends(validar_csrf)])
async def finalizar(request: Request, manutencao_id: str, acao: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_finalizar, request, sessao, manutencao_id, acao, await _entrada(request))
