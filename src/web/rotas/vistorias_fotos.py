"""Adicionar fotos a uma vistoria já registrada (entrega ou devolução), em diálogo (HTMX) e em página.

A vistoria do assistente de contrato e a do encerramento nascem sem fotos quando o dono não as tem na hora; aqui ele
completa depois. Valida tudo antes de enviar; se alguma foto falhar no Storage, as outras ficam e o aviso diz quantas."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import formulario_vistoria as formulario, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.web import acoes_vistorias, dados_vistorias
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.envio_fotos import resumo_fotos, separar_formulario
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario
from src.web.rotas.vistorias_registro import _htmx, _uuid_ou_vazio
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _para_fotos_ou_404(vistoria_id):
    dados = dados_vistorias.vistoria_para_fotos(_uuid_ou_vazio(vistoria_id))
    if dados is None:
        raise HTTPException(status_code=404)
    return dados


def _modelo(request):
    return "vistorias/_form_fotos.html" if _htmx(request) else "vistorias/fotos.html"


def _contexto(dados, erros=None, erro_geral=None):
    return {
        "titulo": "Adicionar fotos", "d": dados, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": f"/vistorias/{dados['vistoria']['id']}/fotos", "limite_fotos": formulario.LIMITE_FOTOS,
        "placa": formatar_placa(dados["moto"]["placa"]),
    }


@router.get("/vistorias/{vistoria_id}/fotos")
def formulario_fotos(request: Request, vistoria_id: str, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, _modelo(request), _contexto(_para_fotos_ou_404(vistoria_id)))


def _anexar(request, sessao, vistoria_id, fotos):
    dados = _para_fotos_ou_404(vistoria_id)

    def gravar():
        if not fotos:
            raise ErroDeCampos({"fotos": "Fotos: escolha ao menos uma foto."})
        formulario.validar_fotos(resumo_fotos(fotos))
        falhas = acoes_vistorias.anexar_fotos(dados["vistoria"]["id"], fotos)
        aviso = mensagens.fotos_anexadas(len(fotos) - falhas, falhas)
        return _concluir(request, sessao, f"/vistorias/contrato/{dados['contrato']['id']}", aviso)

    return _devolver_formulario(request, _modelo(request), _contexto(dados), gravar)


@router.post("/vistorias/{vistoria_id}/fotos", dependencies=[Depends(validar_csrf)])
async def anexar(request: Request, vistoria_id: str, sessao: Sessao = Depends(exigir_dono)):
    _, fotos = separar_formulario(await request.form())
    return await run_in_threadpool(_anexar, request, sessao, vistoria_id, fotos)
