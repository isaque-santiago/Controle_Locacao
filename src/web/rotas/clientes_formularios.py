"""Cadastro e edição de clientes em diálogo HTMX."""

import logging

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from src.domain import arquivamento, erros, mensagens
from src.domain.formulario_cliente import ler_cliente
from src.web import acoes_clientes
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.clientes import _cliente_ou_404
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()
logger = logging.getLogger(__name__)


def _valores(cliente=None):
    c = cliente or {}
    return {chave: str(c.get(chave) or "")[:10] if chave in ("cnh_validade", "data_nascimento") else c.get(chave) or "" for chave in (
        "nome", "cpf", "telefone", "whatsapp", "email", "endereco", "cnh_numero", "cnh_categoria", "cnh_validade", "observacoes",
        "nacionalidade", "naturalidade", "estado_civil", "profissao", "data_nascimento", "rg", "rg_orgao", "cep", "referencias",
    )} | {"status": c.get("status") or "ativo"}


@router.get("/clientes/novo")
def novo(request: Request, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, "clientes/_form_cliente.html", {"nova": True, "acao": "/clientes/novo", "valores": _valores(), "erros": {}})


@router.post("/clientes/novo", dependencies=[Depends(validar_csrf)])
async def cadastrar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    return await run_in_threadpool(_salvar, request, sessao, None, entrada)


@router.get("/clientes/{cliente_id}/editar")
def editar_form(request: Request, cliente_id: str, _: Sessao = Depends(exigir_dono)):
    cliente = _cliente_ou_404(cliente_id)
    return renderizar(request, "clientes/_form_cliente.html", {"nova": False, "acao": f"/clientes/{cliente_id}/editar", "valores": _valores(cliente), "erros": {}})


@router.post("/clientes/{cliente_id}/editar", dependencies=[Depends(validar_csrf)])
async def editar(request: Request, cliente_id: str, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    return await run_in_threadpool(_salvar, request, sessao, cliente_id, entrada)


def _salvar(request, sessao, cliente_id, entrada):
    if cliente_id:
        _cliente_ou_404(cliente_id)
    contexto = {"nova": not cliente_id, "acao": "/clientes/novo" if not cliente_id else f"/clientes/{cliente_id}/editar", "valores": entrada, "erros": {}}
    def acao():
        dados = ler_cliente(entrada)
        salvo = acoes_clientes.atualizar_cliente(cliente_id, dados) if cliente_id else acoes_clientes.criar_cliente(dados)
        destino_id = cliente_id or salvo["id"]
        return _concluir(request, sessao, f"/clientes/{destino_id}", mensagens.cliente_salvo(dados["nome"], novo=not cliente_id))
    return _devolver_formulario(request, "clientes/_form_cliente.html", contexto, acao)


@router.post("/clientes/{cliente_id}/arquivar", dependencies=[Depends(validar_csrf)])
def arquivar(request: Request, cliente_id: str, sessao: Sessao = Depends(exigir_dono)):
    """Arquiva o ex-locatário (botão da ficha com confirmação). Com pendência, recusa e diz qual."""
    cliente = _cliente_ou_404(cliente_id)
    destino = f"/clientes/{cliente_id}"
    try:
        acoes_clientes.arquivar_cliente(cliente_id)
    except ValueError as erro:
        return _concluir(request, sessao, destino, tipo="erro", texto=str(erro))
    except Exception as erro:
        falha = erros.classificar_erro(erro)
        if falha.categoria == erros.SESSAO_EXPIRADA:
            raise
        logger.exception("Falha ao arquivar o cliente %s", cliente_id)
        return _concluir(request, sessao, destino, tipo="erro", texto=falha.mensagem)
    return _concluir(request, sessao, "/clientes", mensagens.cliente_arquivado(cliente["nome"]))


@router.post("/clientes/{cliente_id}/desarquivar", dependencies=[Depends(validar_csrf)])
def desarquivar(request: Request, cliente_id: str, sessao: Sessao = Depends(exigir_dono)):
    cliente = _cliente_ou_404(cliente_id)
    destino = f"/clientes/{cliente_id}"
    if not arquivamento.esta_arquivado(cliente):
        return _concluir(request, sessao, destino, tipo="erro", texto="Este cliente não está arquivado.")
    try:
        acoes_clientes.desarquivar_cliente(cliente_id)
    except Exception as erro:
        falha = erros.classificar_erro(erro)
        if falha.categoria == erros.SESSAO_EXPIRADA:
            raise
        logger.exception("Falha ao desarquivar o cliente %s", cliente_id)
        return _concluir(request, sessao, destino, tipo="erro", texto=falha.mensagem)
    return _concluir(request, sessao, destino, mensagens.cliente_desarquivado(cliente["nome"]))
