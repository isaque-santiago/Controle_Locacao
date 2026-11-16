"""Regras puras do conector do claude.ai (etapa 1 da seção 24 do plano): OAuth 2.1 com PKCE e escopos.

Sem rede nem relógio: o servidor (src/web/rotas/conector.py) cuida de HTTP, sessão e criptografia."""

import base64
import hashlib
import hmac
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Callback fixo dos apps hospedados do Claude (claude.ai na web, Desktop, mobile e Cowork).
REDIRECTS_FIXOS = ("https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback")
ESCOPO_PADRAO = "propor_lancamentos"
ESCOPOS = ("propor_lancamentos", "offline_access")
_VERIFICADOR = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
_LOOPBACK = ("localhost", "127.0.0.1")
LIMITE_REDIRECTS = 5
LIMITE_NOME = 80


class ErroOAuth(ValueError):
    """Erro com o código do OAuth (RFC 6749/7591) e uma mensagem em português."""

    def __init__(self, codigo: str, descricao: str):
        super().__init__(descricao)
        self.codigo = codigo
        self.descricao = descricao


def redirect_permitido(uri: str, permitir_loopback: bool = False) -> bool:
    """Só o callback fixo do Claude; opcionalmente também loopback (testes locais com o MCP Inspector ou o Claude Code)."""
    uri = str(uri or "")
    if uri in REDIRECTS_FIXOS:
        return True
    if not permitir_loopback:
        return False
    partes = urlsplit(uri)
    return partes.scheme == "http" and partes.hostname in _LOOPBACK and not partes.fragment and not partes.username


def validar_registro(corpo, permitir_loopback: bool = False) -> dict:
    """Confere o pedido de registro dinâmico de cliente (RFC 7591). Devolve {"nome", "redirect_uris"}."""
    if not isinstance(corpo, dict):
        raise ErroOAuth("invalid_client_metadata", "O corpo do registro precisa ser um objeto JSON.")
    uris = corpo.get("redirect_uris")
    if not isinstance(uris, list) or not uris or len(uris) > LIMITE_REDIRECTS or not all(isinstance(u, str) for u in uris):
        raise ErroOAuth("invalid_redirect_uri", "Informe de 1 a 5 redirect_uris.")
    if not all(redirect_permitido(u, permitir_loopback) for u in uris):
        raise ErroOAuth("invalid_redirect_uri", "Redirect URI não permitido para este servidor.")
    metodo = corpo.get("token_endpoint_auth_method", "none")
    if metodo != "none":
        raise ErroOAuth("invalid_client_metadata", "Só clientes públicos (token_endpoint_auth_method = none) são aceitos.")
    nome = str(corpo.get("client_name") or "Claude").strip()[:LIMITE_NOME] or "Claude"
    return {"nome": nome, "redirect_uris": list(dict.fromkeys(uris))}


def pkce_confere(verificador: str, desafio: str) -> bool:
    """PKCE com S256: base64url(sha256(verificador)) precisa ser igual ao desafio guardado."""
    if not _VERIFICADOR.match(str(verificador or "")) or not desafio:
        return False
    esperado = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(esperado, str(desafio))


def desafio_pkce_valido(desafio: str, metodo: str) -> bool:
    return metodo == "S256" and bool(re.fullmatch(r"[A-Za-z0-9\-._~]{43,128}", str(desafio or "")))


def escopos_pedidos(texto: str | None) -> str:
    """Escopos pedidos que o servidor conhece, na ordem e sem repetir; sem nenhum, o padrão."""
    pedidos = [e for e in dict.fromkeys(str(texto or "").split()) if e in ESCOPOS]
    return " ".join(pedidos) or ESCOPO_PADRAO


def url_com_parametros(base: str, **parametros) -> str:
    """Acrescenta parâmetros à query de `base` (ignora os vazios), preservando os que já existem."""
    partes = urlsplit(base)
    consulta = parse_qsl(partes.query, keep_blank_values=True) + [(k, v) for k, v in parametros.items() if v not in (None, "")]
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(consulta), ""))


def origem_da_url(url: str) -> str:
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}"
