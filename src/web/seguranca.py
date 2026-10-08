"""Cabeçalhos de segurança e comparação segura de tokens CSRF.

Os cabeçalhos saem da própria aplicação (o proxy do Coolify/Traefik não os define), então
valem em qualquer hospedagem. A CSP não aceita script nem estilo inline: todo JS e CSS
vêm de arquivos em /static.
"""

import secrets
from functools import lru_cache
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
_UM_ANO = 31536000


@lru_cache(maxsize=1)
def politica_de_conteudo() -> str:
    """CSP da aplicação. As fotos das vistorias vêm por URL assinada do Storage do Supabase (outra origem),
    então só essa origem é liberada em `img-src`; sem a URL configurada, vale a política fixa."""
    try:
        from src.config import get_supabase_url

        partes = urlsplit(get_supabase_url())
        origem = f"{partes.scheme}://{partes.netloc}" if partes.scheme in ("http", "https") and partes.netloc else None
    except Exception:
        origem = None
    if not origem:
        return CONTENT_SECURITY_POLICY
    return CONTENT_SECURITY_POLICY.replace("img-src 'self' data:", f"img-src 'self' data: {origem}")


def eh_https(request: Request) -> bool:
    """True quando a requisição chegou por HTTPS (direto ou pelo proxy, via uvicorn --proxy-headers)."""
    return request.url.scheme == "https"


def tokens_iguais(esperado: str | None, recebido: str | None) -> bool:
    if not esperado or not recebido:
        return False
    return secrets.compare_digest(esperado.encode(), recebido.encode())


class CabecalhosSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resposta = await call_next(request)
        cabecalhos = resposta.headers
        cabecalhos["Content-Security-Policy"] = politica_de_conteudo()
        cabecalhos["X-Content-Type-Options"] = "nosniff"
        cabecalhos["X-Frame-Options"] = "DENY"
        cabecalhos["Referrer-Policy"] = "same-origin"
        cabecalhos["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if eh_https(request):
            cabecalhos["Strict-Transport-Security"] = f"max-age={_UM_ANO}"
        if not request.url.path.startswith("/static/"):
            # Páginas mostram dados do usuário: nada de cache compartilhado nem do navegador.
            cabecalhos["Cache-Control"] = "no-store"
        return resposta
