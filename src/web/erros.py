"""Tratamento central de erros: páginas de erro, redirecionamento ao login e avisos HTMX."""

import logging
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as ErroHttp

from src.domain import erros
from src.web.dependencias import (
    COOKIE_SESSAO,
    FalhaCsrf,
    NaoAutenticado,
    SemAcesso,
)
from src.web.templates import renderizar, templates

logger = logging.getLogger(__name__)

_TITULOS = {
    400: "Pedido inválido",
    401: "Entre para continuar",
    403: "Acesso não permitido",
    404: "Página não encontrada",
    405: "Ação não permitida",
    429: "Muitas tentativas",
    500: "Algo deu errado",
    503: "Serviço indisponível",
}
_MENSAGENS = {
    400: "Não foi possível entender o pedido. Volte e confira os dados.",
    403: "Seu acesso não permite abrir esta página.",
    404: "O endereço não existe ou a página foi movida.",
    405: "Esta ação não está disponível neste endereço.",
    429: "Aguarde um pouco antes de tentar de novo.",
    500: "Não foi possível concluir a operação. Tente novamente em instantes.",
    503: erros.MENSAGEM_INDISPONIVEL,
}
MENSAGEM_CSRF = (
    "Não foi possível validar o formulário. Atualize a página e tente novamente."
)


def _eh_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _resposta_de_erro(request: Request, status: int, mensagem: str | None = None):
    mensagem = mensagem or _MENSAGENS.get(status, _MENSAGENS[500])
    titulo = _TITULOS.get(status, _TITULOS[500])
    if _eh_htmx(request):
        # Mostra o aviso na região #avisos da página, sem trocar o conteúdo.
        corpo = templates.get_template("componentes/aviso_htmx.html").render(
            tipo="erro", mensagem=mensagem
        )
        return HTMLResponse(
            corpo,
            status_code=status,
            headers={"HX-Retarget": "#avisos", "HX-Reswap": "innerHTML"},
        )
    return renderizar(
        request,
        "erro.html",
        {"status": status, "titulo": titulo, "mensagem": mensagem},
        status=status,
    )


def _ir_para_login(request: Request, expirada: bool) -> Response:
    destino = "/login"
    parametros = []
    if expirada:
        parametros.append("expirou=1")
    if request.method == "GET" and request.url.path != "/":
        proximo = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        parametros.append(f"proximo={quote(proximo, safe='')}")
    if parametros:
        destino += "?" + "&".join(parametros)
    if _eh_htmx(request):
        resposta = Response(status_code=401, headers={"HX-Redirect": destino})
    else:
        resposta = RedirectResponse(destino, status_code=303)
    if request.cookies.get(COOKIE_SESSAO):
        resposta.delete_cookie(COOKIE_SESSAO, path="/")
    return resposta


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(NaoAutenticado)
    async def _nao_autenticado(request: Request, erro: NaoAutenticado):
        return _ir_para_login(request, erro.expirada)

    @app.exception_handler(SemAcesso)
    async def _sem_acesso(request: Request, _: SemAcesso):
        return _resposta_de_erro(request, 403)

    @app.exception_handler(FalhaCsrf)
    async def _falha_csrf(request: Request, _: FalhaCsrf):
        return _resposta_de_erro(request, 403, MENSAGEM_CSRF)

    @app.exception_handler(ErroHttp)
    async def _erro_http(request: Request, erro: ErroHttp):
        return _resposta_de_erro(request, erro.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, _: RequestValidationError):
        return _resposta_de_erro(request, 400)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, erro: Exception):
        logger.exception("Erro não tratado em %s %s", request.method, request.url.path, exc_info=erro)
        falha = erros.classificar_erro(erro)
        if falha.categoria == erros.SESSAO_EXPIRADA:
            return _ir_para_login(request, expirada=True)
        status = 503 if falha.recuperavel else 500
        return _resposta_de_erro(request, status, falha.mensagem)
