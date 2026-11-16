"""Dependências das rotas: sessão, papel e CSRF.

`sessao_opcional` roda no laço de eventos (async) de propósito: é ali que o cliente
Supabase da requisição é definido no contexto, e as rotas síncronas (que rodam em
thread, com cópia do contexto) o enxergam por `src.db.get_client()`.
"""

import logging
import threading

from fastapi import Depends, Form, Header, Request
from starlette.concurrency import run_in_threadpool

from src import db
from src.services.autenticacao import (
    PAPEL_DONO,
    PAPEL_LOCATARIO,
    SessaoSupabaseInvalida,
)
from src.web.lacre import COOKIE_LEMBRAR, COOKIE_SESSAO
from src.web.seguranca import tokens_iguais
from src.web.sessao import Sessao

log = logging.getLogger(__name__)
# Refazer sessões a partir do cookie `lembrar` uma de cada vez: o token de renovação é de uso único.
_TRAVA_RESTAURACAO = threading.Lock()
COOKIE_CSRF_LOGIN = "csrf_login"


class NaoAutenticado(Exception):
    """Sem sessão válida. `expirada` indica que havia cookie, mas a sessão não vale mais."""

    def __init__(self, expirada: bool = False):
        super().__init__("Sessão ausente ou expirada.")
        self.expirada = expirada


class SemAcesso(Exception):
    """Usuário autenticado, mas sem direito à área pedida."""


class FalhaCsrf(Exception):
    """Token CSRF ausente ou diferente do esperado."""


def _garantir_tokens_validos(app_state, sessao: Sessao) -> None:
    """Renova o access token perto de vencer e mantém o cliente Supabase da sessão."""
    agora = app_state.relogio()
    if not sessao.access_token_vencendo(agora) and sessao.cliente is not None:
        return
    with sessao.trava:
        if sessao.access_token_vencendo(app_state.relogio()):
            try:
                novos = app_state.servico.renovar(sessao.refresh_token)
            except SessaoSupabaseInvalida:
                app_state.armazem.encerrar(sessao.id)
                raise NaoAutenticado(expirada=True)
            sessao.access_token = novos.access_token
            sessao.refresh_token = novos.refresh_token
            sessao.expira_em = novos.expira_em
            sessao.cliente = None
            sessao.cookie_pendente = True  # o cookie `lembrar` leva o token de renovação: precisa do novo
            app_state.armazem.salvar()
        if sessao.cliente is None:
            sessao.cliente = app_state.servico.cliente(sessao.access_token)


def _restaurar_sessao(request: Request) -> Sessao | None:
    """Refaz a sessão em memória a partir do cookie `lembrar` (depois de um deploy ou reinício). None se não der."""
    estado = request.app.state
    dados = estado.lacre.abrir(request.cookies.get(COOKIE_LEMBRAR))
    if dados is None:
        return None
    with _TRAVA_RESTAURACAO:
        existente = estado.armazem.buscar_por_refresh_token(dados["r"])
        if existente is not None:  # outra requisição simultânea já refez esta sessão
            existente.cookie_pendente = True
            return existente
        try:
            tokens = estado.servico.renovar(dados["r"])
            cliente = estado.servico.cliente(tokens.access_token)
            papel = estado.servico.papel(cliente)
        except SessaoSupabaseInvalida:
            return None  # revogado ("Sair de todos os dispositivos"), senha trocada ou vencido no Supabase
        except Exception:
            log.warning("Não foi possível refazer a sessão a partir do cookie lembrar.", exc_info=True)
            return None
        if tokens.usuario_id != dados["u"] or papel not in (PAPEL_DONO, PAPEL_LOCATARIO):
            return None
        sessao = estado.armazem.criar(
            usuario_id=tokens.usuario_id, email=tokens.email, papel=papel,
            access_token=tokens.access_token, refresh_token=tokens.refresh_token, expira_em=tokens.expira_em,
            criada_em=dados["c"], csrf_token=dados["t"],
        )
        sessao.cliente = cliente
        sessao.cookie_pendente = True
        sessao.refresh_de_origem = dados["r"]
        return sessao


async def sessao_opcional(request: Request) -> Sessao | None:
    """Sessão do cookie (renovando o prazo de inatividade), ou None. Sem sessão em memória, tenta o cookie `lembrar`."""
    estado = request.app.state
    sessao = estado.armazem.obter(request.cookies.get(COOKIE_SESSAO))
    if sessao is None and estado.lacre.ativo and request.cookies.get(COOKIE_LEMBRAR):
        sessao = await run_in_threadpool(_restaurar_sessao, request)
    if sessao is None:
        return None
    await run_in_threadpool(_garantir_tokens_validos, estado, sessao)
    db.definir_cliente_da_requisicao(sessao.cliente)
    db.definir_usuario_da_requisicao(sessao.usuario_id)
    request.state.sessao = sessao
    return sessao


async def exigir_sessao(
    request: Request, sessao: Sessao | None = Depends(sessao_opcional)
) -> Sessao:
    if sessao is None:
        raise NaoAutenticado(expirada=bool(request.cookies.get(COOKIE_SESSAO)))
    return sessao


async def exigir_dono(sessao: Sessao = Depends(exigir_sessao)) -> Sessao:
    if sessao.papel != PAPEL_DONO:
        raise SemAcesso()
    return sessao


async def exigir_locatario(sessao: Sessao = Depends(exigir_sessao)) -> Sessao:
    if sessao.papel != PAPEL_LOCATARIO:
        raise SemAcesso()
    return sessao


async def validar_csrf(
    sessao: Sessao = Depends(exigir_sessao),
    csrf_token: str = Form(""),
    x_csrf_token: str | None = Header(None),
) -> None:
    """Exige o token da sessão no campo do formulário ou no cabeçalho X-CSRF-Token (HTMX)."""
    if not tokens_iguais(sessao.csrf_token, x_csrf_token or csrf_token):
        raise FalhaCsrf()


async def validar_csrf_login(request: Request, csrf_token: str = Form("")) -> None:
    """No login ainda não há sessão: compara o campo do formulário com o cookie (double submit)."""
    if not tokens_iguais(request.cookies.get(COOKIE_CSRF_LOGIN), csrf_token):
        raise FalhaCsrf()
