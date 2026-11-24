"""Conector do claude.ai (etapa 1 da seção 24 do plano): servidor MCP remoto com OAuth, só para provar a viabilidade.

Faz duas coisas, as que o claude.ai exige de um conector personalizado (ver `Arquivos/Projeto_Locação.md`, seção 24):
- **OAuth 2.1** com registro dinâmico de cliente (DCR) e PKCE S256: o dono entra com o login normal do app e autoriza o Claude;
- **MCP sobre HTTP** (`POST /mcp`, JSON-RPC) com as ferramentas do chat (`src/domain/conector_mcp.py`).

As ferramentas que falam com o banco rodam em `app.state.conector_servico` (`src/services/conector.py`), que entra no Supabase como o usuário
de serviço do conector; sem ele só o `ping` funciona. Sem `CONECTOR_CHAVE`, todas as rotas respondem 404 (conector desligado). O chat grava
cadastros e lançamentos limpos e, na dúvida, recebe o motivo; editar, apagar e aprovar nunca serão ferramentas do conector."""

import json
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from src.domain.conector_mcp import PROTOCOLOS_SUPORTADOS, responder
from src.domain.conector_oauth import (
    ESCOPOS,
    ESCOPO_PADRAO,
    ErroOAuth,
    desafio_pkce_valido,
    escopos_pedidos,
    origem_da_url,
    pkce_confere,
    redirect_permitido,
    url_com_parametros,
    validar_registro,
)
from src.services.autenticacao import PAPEL_DONO
from src.web.dependencias import exigir_sessao, sessao_opcional, validar_csrf
from src.web.selos_conector import VALIDADE_ACESSO, VALIDADE_CLIENTE, VALIDADE_CODIGO, VALIDADE_RENOVACAO
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()

_SEM_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
_ORIGENS_DO_CLAUDE = ("https://claude.ai", "https://claude.com")
_PAGINA = "conector/autorizar.html"


class _ErroDaPagina(Exception):
    """Pedido de autorização que não pode voltar ao cliente por redirect (client_id ou redirect_uri inválidos)."""


def _desligado() -> Response:
    return JSONResponse({"error": "not_found"}, status_code=404)


def _ligado(request: Request):
    conector = request.app.state.conector
    return conector if conector.ativo else None


def _base(request: Request, conector) -> str:
    return conector.url_base or str(request.base_url).rstrip("/")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def _bloqueado(request: Request, chave: str) -> int:
    return request.app.state.limitador_conector.segundos_de_bloqueio(f"{chave}:{_ip(request)}")


def _falha(request: Request, chave: str) -> None:
    request.app.state.limitador_conector.registrar_falha(f"{chave}:{_ip(request)}")


def _erro_json(codigo: str, descricao: str, status: int = 400, **cabecalhos) -> JSONResponse:
    return JSONResponse({"error": codigo, "error_description": descricao}, status_code=status, headers={**_SEM_CACHE, **cabecalhos})


def _muitas_tentativas(espera: int) -> JSONResponse:
    return _erro_json("invalid_request", "Muitas tentativas. Tente de novo em alguns minutos.", 429, **{"Retry-After": str(espera)})


# ---------------------------------------------------------------- descoberta

@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def recurso_protegido(request: Request):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    base = _base(request, conector)
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "scopes_supported": list(ESCOPOS),
        "bearer_methods_supported": ["header"],
        "resource_name": "LA Locadora",
    })


@router.get("/.well-known/oauth-authorization-server")
async def servidor_de_autorizacao(request: Request):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    base = _base(request, conector)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": list(ESCOPOS),
    })


# ---------------------------------------------------------------- registro do cliente (DCR)

@router.post("/oauth/register")
async def registrar_cliente(request: Request):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    if espera := _bloqueado(request, "registro"):
        return _muitas_tentativas(espera)
    _falha(request, "registro")  # cada registro conta: o uso legítimo é raro
    try:
        corpo = await request.json()
    except ValueError:
        corpo = None
    try:
        cliente = validar_registro(corpo, conector.permitir_loopback)
    except ErroOAuth as erro:
        return _erro_json(erro.codigo, erro.descricao)
    client_id = conector.selar("cli", {"ru": cliente["redirect_uris"], "n": cliente["nome"]}, VALIDADE_CLIENTE)
    return JSONResponse({
        "client_id": client_id,
        "client_name": cliente["nome"],
        "redirect_uris": cliente["redirect_uris"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }, status_code=201, headers=_SEM_CACHE)


# ---------------------------------------------------------------- autorização (o dono entra e consente)

def _cliente_e_redirect(conector, p: dict) -> tuple[dict, str]:
    """Confere client_id e redirect_uri. Se falhar, NÃO se redireciona (o redirect_uri não é confiável)."""
    cliente = conector.abrir("cli", p.get("client_id"))
    if not cliente:
        raise _ErroDaPagina("Cliente desconhecido. Remova o conector no Claude e adicione de novo.")
    uri = p.get("redirect_uri", "")
    if uri not in cliente["ru"] or not redirect_permitido(uri, conector.permitir_loopback):
        raise _ErroDaPagina("Endereço de retorno não autorizado para este cliente.")
    return cliente, uri


def _erro_do_pedido(p: dict) -> tuple[str, str] | None:
    if p.get("response_type") != "code":
        return "unsupported_response_type", "Só response_type=code é aceito."
    if not desafio_pkce_valido(p.get("code_challenge"), p.get("code_challenge_method")):
        return "invalid_request", "PKCE com S256 é obrigatório."
    return None


def _voltar_com_erro(uri: str, p: dict, codigo: str, descricao: str) -> RedirectResponse:
    return RedirectResponse(url_com_parametros(uri, error=codigo, error_description=descricao, state=p.get("state")), status_code=303)


@router.get("/oauth/authorize")
async def autorizar(request: Request, sessao: Sessao | None = Depends(sessao_opcional)):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    p = {k: v for k, v in request.query_params.items()}
    try:
        cliente, uri = _cliente_e_redirect(conector, p)
    except _ErroDaPagina as erro:
        return renderizar(request, _PAGINA, {"titulo": "Autorizar o Claude", "erro": str(erro)}, status=400)
    if sessao is None:
        destino = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse("/login?" + urlencode({"proximo": destino}), status_code=303)
    if sessao.papel != PAPEL_DONO:
        return renderizar(request, _PAGINA, {"titulo": "Autorizar o Claude", "erro": "Só os usuários donos podem autorizar o conector."}, status=403)
    if falha := _erro_do_pedido(p):
        return _voltar_com_erro(uri, p, *falha)
    # O formulário envia ao app e este redireciona ao Claude: o CSP (form-action) precisa liberar só essa origem, só nesta página.
    request.state.form_action_extra = origem_da_url(uri)
    campos = {k: p.get(k, "") for k in ("client_id", "redirect_uri", "response_type", "code_challenge", "code_challenge_method", "state", "scope")}
    return renderizar(request, _PAGINA, {
        "titulo": "Autorizar o Claude", "erro": "", "campos": campos, "nome_cliente": cliente["n"], "destino": origem_da_url(uri),
        "escopo": escopos_pedidos(p.get("scope")),
    })


@router.post("/oauth/authorize", dependencies=[Depends(validar_csrf)])
async def confirmar_autorizacao(request: Request, sessao: Sessao = Depends(exigir_sessao)):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    form = await request.form()
    p = {k: str(v) for k, v in form.items()}
    try:
        _, uri = _cliente_e_redirect(conector, p)  # tudo conferido de novo: os campos escondidos vêm do navegador
    except _ErroDaPagina as erro:
        return renderizar(request, _PAGINA, {"titulo": "Autorizar o Claude", "erro": str(erro)}, status=400)
    if sessao.papel != PAPEL_DONO:
        return renderizar(request, _PAGINA, {"titulo": "Autorizar o Claude", "erro": "Só os usuários donos podem autorizar o conector."}, status=403)
    if falha := _erro_do_pedido(p):
        return _voltar_com_erro(uri, p, *falha)
    if p.get("decisao") != "autorizar":
        return _voltar_com_erro(uri, p, "access_denied", "O proprietário negou o acesso.")
    codigo = conector.selar("cod", {
        "sub": sessao.usuario_id, "cid": p["client_id"], "ru": uri, "cc": p["code_challenge"], "sc": escopos_pedidos(p.get("scope")),
    }, VALIDADE_CODIGO)
    logger.info("Conector: autorização concedida ao Claude.")
    return RedirectResponse(url_com_parametros(uri, code=codigo, state=p.get("state")), status_code=303)


# ---------------------------------------------------------------- tokens

def _emitir(conector, sub: str, cid: str, escopo: str) -> JSONResponse:
    dados = {"sub": sub, "cid": cid, "sc": escopo}
    return JSONResponse({
        "access_token": conector.selar("acc", dados, VALIDADE_ACESSO),
        "token_type": "Bearer",
        "expires_in": VALIDADE_ACESSO,
        "refresh_token": conector.selar("ref", dados, VALIDADE_RENOVACAO),
        "scope": escopo or ESCOPO_PADRAO,
    }, headers=_SEM_CACHE)


@router.post("/oauth/token")
async def token(request: Request):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    if espera := _bloqueado(request, "token"):
        return _muitas_tentativas(espera)
    if "application/x-www-form-urlencoded" not in request.headers.get("content-type", ""):
        return _erro_json("invalid_request", "Use Content-Type: application/x-www-form-urlencoded.")
    form = await request.form()
    p = {k: str(v) for k, v in form.items()}

    def recusar(codigo: str, descricao: str, status: int = 400):
        _falha(request, "token")
        return _erro_json(codigo, descricao, status)

    client_id = p.get("client_id", "")
    if not conector.abrir("cli", client_id):
        return recusar("invalid_client", "Cliente desconhecido.", 401)
    concessao = p.get("grant_type")
    if concessao == "authorization_code":
        carga = conector.abrir("cod", p.get("code"))
        if not carga or carga["cid"] != client_id or carga["ru"] != p.get("redirect_uri") or not pkce_confere(p.get("code_verifier", ""), carga["cc"]):
            return recusar("invalid_grant", "Código inválido, vencido ou já usado.")
    elif concessao == "refresh_token":
        carga = conector.abrir("ref", p.get("refresh_token"))
        if not carga or carga["cid"] != client_id:
            return recusar("invalid_grant", "Token de renovação inválido ou vencido.")
    else:
        return recusar("unsupported_grant_type", "Só authorization_code e refresh_token são aceitos.")
    if not conector.consumir(carga):  # código e token de renovação valem uma vez só (o novo par substitui o antigo)
        return recusar("invalid_grant", "Código ou token de renovação já usado.")
    return _emitir(conector, carga["sub"], carga["cid"], carga["sc"])


# ---------------------------------------------------------------- MCP

def _nao_autenticado(request: Request, conector, invalido: bool) -> Response:
    base = _base(request, conector)
    desafio = f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource/mcp", scope="{ESCOPO_PADRAO}"'
    if invalido:
        desafio += ', error="invalid_token"'
    return Response(status_code=401, headers={"WWW-Authenticate": desafio, **_SEM_CACHE})


def _executor_seguro(servico):
    """O executor das ferramentas, que nunca deixa uma falha inesperada virar erro HTTP nem vazar detalhe para o chat."""
    if servico is None:
        return None

    def executar(nome, argumentos):
        try:
            return servico.executar(nome, argumentos)
        except Exception:
            logger.exception("Conector: falha inesperada na ferramenta %s", nome)
            return {"texto": "Não foi possível falar com o sistema agora. Nada foi gravado; tente de novo em instantes.", "erro": True}

    return executar


@router.get("/mcp")
@router.delete("/mcp")
async def mcp_metodo_nao_permitido(request: Request):
    if not _ligado(request):
        return _desligado()
    return Response(status_code=405, headers={"Allow": "POST"})


@router.post("/mcp")
async def mcp(request: Request):
    conector = _ligado(request)
    if not conector:
        return _desligado()
    origem = request.headers.get("origin")
    if origem and origem not in (*_ORIGENS_DO_CLAUDE, _base(request, conector)):
        return Response(status_code=403)  # protege contra páginas de terceiros chamando o conector pelo navegador do dono
    if espera := _bloqueado(request, "mcp"):
        return _muitas_tentativas(espera)
    autorizacao = request.headers.get("authorization", "")
    bearer = autorizacao[7:].strip() if autorizacao.lower().startswith("bearer ") else ""
    if not bearer:
        return _nao_autenticado(request, conector, invalido=False)
    if not conector.abrir("acc", bearer):
        _falha(request, "mcp")
        return _nao_autenticado(request, conector, invalido=True)
    try:
        corpo = json.loads(await request.body())
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido."}}, status_code=400)
    mensagens = corpo if isinstance(corpo, list) else [corpo]
    if not mensagens or len(mensagens) > 20:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Lote inválido."}}, status_code=400)
    executar = _executor_seguro(request.app.state.conector_servico)
    respostas = []
    for m in mensagens:
        resposta = await run_in_threadpool(responder, m, executar)  # as ferramentas falam com o banco (chamadas síncronas)
        if resposta is not None:
            respostas.append(resposta)
    logger.info("Conector MCP: %s", ",".join(str(m.get("method")) for m in mensagens if isinstance(m, dict)))
    if not respostas:
        return Response(status_code=202)
    return JSONResponse(respostas if isinstance(corpo, list) else respostas[0], headers=_SEM_CACHE)
