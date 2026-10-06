"""Login e logout."""

import logging
import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from src.domain import erros
from src.domain.acesso_locatario import identificador_para_email
from src.services.autenticacao import (
    PAPEL_DONO,
    PAPEL_LOCATARIO,
    CredenciaisInvalidas,
)
from src.web.apresentacao import destino_seguro
from src.web.dependencias import (
    COOKIE_CSRF_LOGIN,
    COOKIE_SESSAO,
    sessao_opcional,
    validar_csrf,
    validar_csrf_login,
)
from src.web.seguranca import eh_https
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()

MENSAGEM_CREDENCIAIS = "E-mail, CPF ou senha inválidos."
MENSAGEM_CAMPOS = "Informe o e-mail ou CPF e a senha."
MENSAGEM_SEM_PERMISSAO = (
    "Esta conta não tem acesso ao sistema. Fale com o proprietário."
)
MENSAGEM_NAO_CONFIGURADO = (
    "O aplicativo não está configurado. Confira as credenciais do Supabase."
)
MENSAGEM_EXPIRADA = "A sessão expirou por inatividade. Entre novamente."


def _inicio_do_papel(papel: str) -> str:
    return "/portal" if papel == PAPEL_LOCATARIO else "/"


def _chave_identificador(identificador: str) -> str:
    return "id:" + identificador_para_email(identificador).strip().lower()


def _minutos(segundos: int) -> int:
    return max(1, -(-segundos // 60))


def _pagina_login(
    request: Request,
    *,
    csrf_login: str,
    erro: str = "",
    identificador: str = "",
    proximo: str = "/",
    status: int = 200,
    aviso: str = "",
):
    resposta = renderizar(
        request,
        "login.html",
        {
            "erro": erro,
            "mensagem_aviso": aviso,
            "identificador": identificador,
            "proximo": proximo,
            "csrf_login": csrf_login,
        },
        status=status,
    )
    resposta.set_cookie(
        COOKIE_CSRF_LOGIN,
        csrf_login,
        httponly=True,
        secure=eh_https(request),
        samesite="lax",
        path="/login",
    )
    return resposta


@router.get("/login")
def pagina_login(
    request: Request,
    proximo: str = "/",
    expirou: str = "",
    sessao: Sessao | None = Depends(sessao_opcional),
):
    if sessao is not None:
        return RedirectResponse(_inicio_do_papel(sessao.papel), status_code=303)
    csrf_login = request.cookies.get(COOKIE_CSRF_LOGIN) or secrets.token_urlsafe(32)
    return _pagina_login(
        request,
        csrf_login=csrf_login,
        proximo=destino_seguro(proximo),
        aviso=MENSAGEM_EXPIRADA if expirou else "",
    )


@router.post("/login", dependencies=[Depends(validar_csrf_login)])
def entrar(
    request: Request,
    identificador: str = Form(""),
    senha: str = Form(""),
    proximo: str = Form("/"),
    csrf_token: str = Form(""),
):
    estado = request.app.state
    proximo = destino_seguro(proximo)
    contexto = {"csrf_login": csrf_token, "identificador": identificador, "proximo": proximo}

    if not identificador.strip() or not senha:
        return _pagina_login(request, erro=MENSAGEM_CAMPOS, status=400, **contexto)

    ip = request.client.host if request.client else "desconhecido"
    chave_id = _chave_identificador(identificador)
    espera = max(
        estado.limitador_ip.segundos_de_bloqueio(f"ip:{ip}"),
        estado.limitador_identificador.segundos_de_bloqueio(chave_id),
    )
    if espera:
        mensagem = f"Muitas tentativas. Tente novamente em {_minutos(espera)} min."
        resposta = _pagina_login(request, erro=mensagem, status=429, **contexto)
        resposta.headers["Retry-After"] = str(espera)
        return resposta

    try:
        tokens = estado.servico.entrar(identificador, senha)
        cliente = estado.servico.cliente(tokens.access_token)
        papel = estado.servico.papel(cliente)
    except CredenciaisInvalidas:
        estado.limitador_ip.registrar_falha(f"ip:{ip}")
        estado.limitador_identificador.registrar_falha(chave_id)
        return _pagina_login(request, erro=MENSAGEM_CREDENCIAIS, status=401, **contexto)
    except RuntimeError as falha:
        logger.error("Configuração do Supabase ausente: %s", falha)
        return _pagina_login(request, erro=MENSAGEM_NAO_CONFIGURADO, status=503, **contexto)
    except Exception as falha:
        logger.exception("Falha ao entrar")
        classificada = erros.classificar_erro(falha)
        return _pagina_login(request, erro=classificada.mensagem, status=503, **contexto)

    if papel not in (PAPEL_DONO, PAPEL_LOCATARIO):
        estado.servico.sair(tokens.access_token)
        return _pagina_login(request, erro=MENSAGEM_SEM_PERMISSAO, status=403, **contexto)

    estado.limitador_identificador.limpar(chave_id)
    sessao = estado.armazem.criar(
        usuario_id=tokens.usuario_id,
        email=tokens.email,
        papel=papel,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expira_em=tokens.expira_em,
    )
    sessao.cliente = cliente

    destino = proximo if papel == PAPEL_DONO else "/portal"
    resposta = RedirectResponse(destino, status_code=303)
    resposta.set_cookie(
        COOKIE_SESSAO,
        sessao.id,
        httponly=True,
        secure=eh_https(request),
        samesite="lax",
        path="/",
    )
    resposta.delete_cookie(COOKIE_CSRF_LOGIN, path="/login")
    return resposta


@router.post("/logout", dependencies=[Depends(validar_csrf)])
def sair(request: Request):
    estado = request.app.state
    sessao = estado.armazem.encerrar(request.cookies.get(COOKIE_SESSAO))
    if sessao is not None:
        estado.servico.sair(sessao.access_token)
    resposta = RedirectResponse("/login", status_code=303)
    resposta.delete_cookie(COOKIE_SESSAO, path="/")
    return resposta
