"""Cabeçalhos de segurança e comparação segura de tokens CSRF.

Os cabeçalhos saem da própria aplicação (o proxy do Coolify/Traefik não os define), então
valem em qualquer hospedagem. A CSP não aceita script nem estilo inline: todo JS e CSS
vêm de arquivos em /static.
"""

import secrets

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
        cabecalhos["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
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
