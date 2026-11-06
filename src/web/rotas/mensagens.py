"""Mensagens de WhatsApp enviadas aos locatários: lista com filtro por situação e as ações cancelar e reenviar (seção 20).

Só o dono vê e age. O texto das mensagens tem dados pessoais, então a página nunca vai para cache (a regra já vale para todo o painel)."""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import mensagens as avisos
from src.domain import whatsapp_painel as regras
from src.domain.paginacao import OPCOES_POR_PAGINA, calcular_pagina
from src.web import acoes_whatsapp, dados_whatsapp
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _inteiro(valor, padrao):
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def _url(filtro: str, pagina: int = 1) -> str:
    parametros = {}
    if filtro != regras.FILTROS[0][0]:
        parametros["filtro"] = filtro
    if pagina > 1:
        parametros["pagina"] = pagina
    return "/mensagens" + (f"?{urlencode(parametros)}" if parametros else "")


@router.get("/mensagens")
def lista(request: Request, filtro: str | None = None, pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    filtro = regras.filtro_valido(filtro)
    dados = dados_whatsapp.mensagens(filtro)
    recorte = calcular_pagina(len(dados["itens"]), _inteiro(pagina, 1), OPCOES_POR_PAGINA[0])
    itens = [
        {**m, "assuntos": regras.assuntos(m), "pode_cancelar": regras.pode_cancelar(m), "pode_reenviar": regras.pode_reenviar(m)}
        for m in dados["itens"][recorte.inicio:recorte.fim]
    ]
    contexto = {
        "titulo": "Mensagens", "itens": itens, "pagina": recorte, "filtro": filtro, "contagem": dados["contagem"],
        "chips": [(chave, rotulo, dados["contagem"][chave], _url(chave)) for chave, rotulo in regras.FILTROS],
        "url_anterior": _url(filtro, recorte.pagina - 1) if recorte.tem_anterior else None,
        "url_proxima": _url(filtro, recorte.pagina + 1) if recorte.tem_proxima else None,
        "status_rotulo": regras.STATUS_ROTULO, "status_tom": regras.STATUS_TOM,
        "voltar_para": _url(filtro, recorte.pagina),
    }
    return renderizar(request, "mensagens/lista.html", contexto)


def _id_valido(mensagem_id: str) -> str:
    try:
        UUID(mensagem_id)
    except ValueError:
        raise HTTPException(status_code=404)
    return mensagem_id


async def _agir(request: Request, sessao: Sessao, mensagem_id: str, acao, aviso):
    destino = (await request.form()).get("voltar_para") or "/mensagens"
    if not destino.startswith("/mensagens"):  # só volta para esta página
        destino = "/mensagens"
    try:
        await run_in_threadpool(acao, _id_valido(mensagem_id))
    except ValueError as erro:
        return _concluir(request, sessao, destino, tipo="atencao", texto=str(erro))
    return _concluir(request, sessao, destino, aviso())


@router.post("/mensagens/{mensagem_id}/cancelar", dependencies=[Depends(validar_csrf)])
async def cancelar(request: Request, mensagem_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await _agir(request, sessao, mensagem_id, acoes_whatsapp.cancelar, avisos.whatsapp_cancelada)


@router.post("/mensagens/{mensagem_id}/reenviar", dependencies=[Depends(validar_csrf)])
async def reenviar(request: Request, mensagem_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await _agir(request, sessao, mensagem_id, acoes_whatsapp.reenviar, avisos.whatsapp_reenviada)
