"""Aba WhatsApp da ficha do cliente: o dono para ou volta a enviar as mensagens automáticas daquele cliente (seção 20).

Só o dono decide: o cliente não tem como parar as mensagens por conta própria, porque são os avisos de cobrança e de vencimentos."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import erros, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.domain.formulario_whatsapp import ler_bloqueio
from src.web import acoes_whatsapp
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.clientes import _cliente_ou_404, _contexto_aba
from src.web.rotas.motos_formularios import _concluir, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()


def _painel(request, cliente, erros_whatsapp=None, motivo="", status=200):
    contexto = _contexto_aba(cliente, "whatsapp") | {"erros_whatsapp": erros_whatsapp, "motivo_digitado": motivo}
    resposta = renderizar(request, "clientes/_resposta_aba.html", contexto, status=status)
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def _falha(request, erro):
    falha = erros.classificar_erro(erro)
    if falha.categoria == erros.SESSAO_EXPIRADA:
        raise erro
    logger.exception("Falha no bloqueio de WhatsApp em %s", request.url.path)
    return falha.mensagem


def _bloquear(request, sessao, cliente_id, entrada):
    cliente = _cliente_ou_404(cliente_id)
    destino = f"/clientes/{cliente_id}?aba=whatsapp"
    try:
        motivo = ler_bloqueio(entrada)
    except ErroDeCampos as erro:
        return _painel(request, cliente, erro.erros, entrada.get("motivo", ""), status=422)
    try:
        acoes_whatsapp.bloquear(cliente_id, motivo)
    except HTTPException:
        raise
    except Exception as erro:
        return _concluir(request, sessao, destino, tipo="erro", texto=_falha(request, erro))
    return _concluir(request, sessao, destino, mensagens.whatsapp_cliente_bloqueado(cliente["nome"]))


def _liberar(request, sessao, cliente_id):
    cliente = _cliente_ou_404(cliente_id)
    destino = f"/clientes/{cliente_id}?aba=whatsapp"
    try:
        acoes_whatsapp.desbloquear(cliente_id)
    except HTTPException:
        raise
    except Exception as erro:
        return _concluir(request, sessao, destino, tipo="erro", texto=_falha(request, erro))
    return _concluir(request, sessao, destino, mensagens.whatsapp_cliente_liberado(cliente["nome"]))


@router.post("/clientes/{cliente_id}/whatsapp/bloquear", dependencies=[Depends(validar_csrf)])
async def bloquear(request: Request, cliente_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_bloquear, request, sessao, cliente_id, await _entrada(request))


@router.post("/clientes/{cliente_id}/whatsapp/liberar", dependencies=[Depends(validar_csrf)])
async def liberar(request: Request, cliente_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_liberar, request, sessao, cliente_id)
