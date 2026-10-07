"""Cadastro e edição dos itens do catálogo de manutenção."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import formulario_manutencao as formulario, mensagens
from src.web import acoes_manutencao, dados_manutencao
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _item_ou_404(item_id):
    item = dados_manutencao.obter_item(item_id)
    if item is None:
        raise HTTPException(status_code=404)
    return item


def _contexto(item, valores, erros=None, erro_geral=None):
    novo = item is None
    return {
        "titulo": "Novo item do catálogo" if novo else "Editar item do catálogo",
        "novo": novo, "item": item, "v": valores, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": "/manutencao/catalogo/novo" if novo else f"/manutencao/catalogo/{item['id']}/editar",
    }


@router.get("/manutencao/catalogo/novo")
def novo(request: Request, _: Sessao = Depends(exigir_dono)):
    contexto = _contexto(None, formulario.valores_item_catalogo())
    return renderizar(request, "manutencao/_form_catalogo.html" if _htmx(request) else "manutencao/catalogo_form.html", contexto)


@router.get("/manutencao/catalogo/{item_id}/editar")
def editar(request: Request, item_id: str, _: Sessao = Depends(exigir_dono)):
    item = _item_ou_404(item_id)
    contexto = _contexto(item, formulario.valores_item_catalogo(item))
    return renderizar(request, "manutencao/_form_catalogo.html" if _htmx(request) else "manutencao/catalogo_form.html", contexto)


def _salvar(request, sessao, item, entrada):
    valores = {**entrada, "ativo": bool(entrada.get("ativo"))}
    contexto = _contexto(item, valores)

    def gravar():
        dados = formulario.ler_item_catalogo(valores)
        if item is None:
            acoes_manutencao.criar_item(dados)
        else:
            acoes_manutencao.atualizar_item(item["id"], dados)
        return _concluir(request, sessao, "/manutencao?aba=catalogo", mensagens.item_catalogo_salvo(dados["nome"], novo=item is None))

    modelo = "manutencao/_form_catalogo.html" if _htmx(request) else "manutencao/catalogo_form.html"
    return _devolver_formulario(request, modelo, contexto, gravar)


@router.post("/manutencao/catalogo/novo", dependencies=[Depends(validar_csrf)])
async def criar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_salvar, request, sessao, None, await _entrada(request))


@router.post("/manutencao/catalogo/{item_id}/editar", dependencies=[Depends(validar_csrf)])
async def atualizar(request: Request, item_id: str, sessao: Sessao = Depends(exigir_dono)):
    item = await run_in_threadpool(_item_ou_404, item_id)
    return await run_in_threadpool(_salvar, request, sessao, item, await _entrada(request))
