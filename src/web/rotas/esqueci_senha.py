"""«Esqueci minha senha» do portal do locatário (tela pública, sem login).

O e-mail do portal é fictício, então não há link de redefinição: o locatário informa o CPF e isso registra um pedido que aparece para o
dono, que gera a senha nova e a entrega pessoalmente. A resposta é a mesma para qualquer CPF válido (tenha acesso ao portal ou não), para
ninguém descobrir quem é cliente. O CSRF usa o mesmo cookie do login (`csrf_login`, caminho `/login`), por isso a rota fica sob `/login`.
Cada pedido conta no limite por IP, senão a tela serviria para enchê-lo de pedidos."""

import logging
import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from src.domain import erros
from src.domain.formulario_moto import ErroDeCampos
from src.domain.pedido_senha import MENSAGEM_PEDIDO, ler_cpf
from src.web.dependencias import COOKIE_CSRF_LOGIN, sessao_opcional, validar_csrf_login
from src.web.seguranca import eh_https
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()


def _minutos(segundos: int) -> int:
    return max(1, -(-segundos // 60))


def _pagina(request, csrf_login, *, cpf="", erros_campos=None, erro="", pedido_feito=False, status=200):
    resposta = renderizar(
        request, "esqueci_senha.html",
        {"titulo": "Esqueci minha senha", "cpf": cpf, "erros": erros_campos or {}, "erro": erro, "pedido_feito": pedido_feito,
         "mensagem_pedido": MENSAGEM_PEDIDO, "csrf_login": csrf_login},
        status=status,
    )
    resposta.set_cookie(COOKIE_CSRF_LOGIN, csrf_login, httponly=True, secure=eh_https(request), samesite="lax", path="/login")
    return resposta


@router.get("/login/esqueci-senha")
def formulario(request: Request, sessao: Sessao | None = Depends(sessao_opcional)):
    if sessao is not None:
        return RedirectResponse("/", status_code=303)
    return _pagina(request, request.cookies.get(COOKIE_CSRF_LOGIN) or secrets.token_urlsafe(32))


@router.post("/login/esqueci-senha", dependencies=[Depends(validar_csrf_login)])
def pedir(request: Request, cpf: str = Form(""), csrf_token: str = Form("")):
    estado = request.app.state
    ip = request.client.host if request.client else "desconhecido"
    chave = f"senha:{ip}"
    espera = estado.limitador_ip.segundos_de_bloqueio(chave)
    if espera:
        resposta = _pagina(request, csrf_token, cpf=cpf, erro=f"Muitos pedidos. Tente novamente em {_minutos(espera)} min.", status=429)
        resposta.headers["Retry-After"] = str(espera)
        return resposta
    estado.limitador_ip.registrar_falha(chave)  # todo pedido conta, tenha o CPF acesso ou não

    try:
        digitos = ler_cpf({"cpf": cpf})
    except ErroDeCampos as erro:
        return _pagina(request, csrf_token, cpf=cpf, erros_campos=erro.erros, status=400)
    try:
        estado.servico.pedir_senha_nova(digitos)
    except Exception as falha:
        logger.exception("Falha ao registrar o pedido de senha nova")
        return _pagina(request, csrf_token, cpf=cpf, erro=erros.classificar_erro(falha).mensagem, status=503)
    return _pagina(request, csrf_token, pedido_feito=True)
