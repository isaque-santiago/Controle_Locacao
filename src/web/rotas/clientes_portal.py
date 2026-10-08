"""Aba Portal da ficha do cliente: criar, redefinir e remover o acesso do locatário e abrir as fotos das trocas.

A senha gerada só existe na resposta do POST: vai direto ao painel, sem sessão, URL, log ou cache."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from src.domain import erros, mensagens
from src.web import acoes_clientes, dados_clientes
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.clientes import _cliente_ou_404, _contexto_aba
from src.web.rotas.motos_formularios import _concluir
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()

_FOTOS = {"painel": "foto_painel_path", "nota": "nota_fiscal_path"}


def _painel_portal(request, cliente, credenciais=None, erro=None):
    contexto = _contexto_aba(cliente, "portal") | {"credenciais": credenciais, "erro_portal": erro}
    resposta = renderizar(request, "clientes/_resposta_aba.html", contexto, status=422 if erro else 200)
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def _mensagem_da_falha(request, erro):
    """Texto para o dono; a sessão expirada sobe para o tratamento padrão (volta ao login)."""
    falha = erros.classificar_erro(erro)
    if falha.categoria == erros.SESSAO_EXPIRADA:
        raise erro
    logger.exception("Falha no acesso ao portal em %s", request.url.path)
    return falha.mensagem


def _gerar(request, cliente_id, acao):
    cliente = _cliente_ou_404(cliente_id)
    try:
        return _painel_portal(request, cliente, credenciais=acao(cliente_id))
    except ValueError as erro:
        return _painel_portal(request, cliente, erro=str(erro))
    except HTTPException:
        raise
    except Exception as erro:
        return _painel_portal(request, cliente, erro=_mensagem_da_falha(request, erro))


@router.post("/clientes/{cliente_id}/portal/acesso", dependencies=[Depends(validar_csrf)])
async def criar_acesso(request: Request, cliente_id: str, _: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_gerar, request, cliente_id, acoes_clientes.criar_acesso_portal)


@router.post("/clientes/{cliente_id}/portal/senha", dependencies=[Depends(validar_csrf)])
async def redefinir_senha(request: Request, cliente_id: str, _: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_gerar, request, cliente_id, acoes_clientes.redefinir_senha_portal)


def _remover(request, sessao, cliente_id):
    cliente = _cliente_ou_404(cliente_id)
    destino = f"/clientes/{cliente_id}?aba=portal"
    try:
        acoes_clientes.remover_acesso_portal(cliente_id)
    except ValueError as erro:
        return _concluir(request, sessao, destino, tipo="erro", texto=str(erro))
    except HTTPException:
        raise
    except Exception as erro:
        return _concluir(request, sessao, destino, tipo="erro", texto=_mensagem_da_falha(request, erro))
    return _concluir(request, sessao, destino, mensagens.acesso_portal_removido(cliente["nome"]))


@router.post("/clientes/{cliente_id}/portal/remover", dependencies=[Depends(validar_csrf)])
async def remover_acesso(request: Request, cliente_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_remover, request, sessao, cliente_id)


def _url_da_foto(cliente_id, troca_id, foto):
    if foto not in _FOTOS:
        raise HTTPException(status_code=404)
    try:
        UUID(troca_id)
    except ValueError:
        raise HTTPException(status_code=404)
    _cliente_ou_404(cliente_id)
    troca = next((t for t in dados_clientes.listar_trocas(cliente_id) if str(t["id"]) == troca_id), None)
    caminho = troca.get(_FOTOS[foto]) if troca else None
    if not caminho:
        raise HTTPException(status_code=404)
    return acoes_clientes.url_arquivo_troca(caminho)


@router.get("/clientes/{cliente_id}/portal/trocas/{troca_id}/{foto}")
async def abrir_foto(cliente_id: str, troca_id: str, foto: str, _: Sessao = Depends(exigir_dono)):
    """Redireciona para a URL assinada (5 min): o bucket é privado e a URL não é guardada em lugar nenhum."""
    url = await run_in_threadpool(_url_da_foto, cliente_id, troca_id, foto)
    return RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})
