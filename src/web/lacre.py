"""Cookie "lembrar": a sessão sobrevive a deploys e reinícios do servidor (decisão do dono em 16/11/2026).

As sessões ficam só na memória do servidor, então todo deploy as derrubava. Para o locatário não entrar de novo, o login
também grava no navegador um cookie `lembrar` com o token de renovação do Supabase **criptografado** (Fernet: cifra e
assinatura) com a chave secreta `SESSAO_CHAVE`, que só existe no servidor. Sem a sessão em memória, o app abre o cookie,
renova os tokens no Supabase e refaz a sessão. Nada vai a disco. Sem a chave, o recurso fica desligado e vale o
comportamento antigo (reinício derruba a sessão). "Sair de todos os dispositivos" revoga os tokens no Supabase, e
com isso os cookies `lembrar` deixam de funcionar em qualquer aparelho."""

import json
import logging
import os
from time import time
from typing import Callable

from cryptography.fernet import Fernet, InvalidToken
from starlette.middleware.base import BaseHTTPMiddleware

from src.domain.sessao_longa import INATIVIDADE_MAXIMA_SEGUNDOS, UM_DIA_SEGUNDOS, VIDA_MAXIMA_SEGUNDOS, sessao_vencida

logger = logging.getLogger(__name__)

COOKIE_SESSAO = "sessao"
COOKIE_LEMBRAR = "lembrar"
VARIAVEL_CHAVE = "SESSAO_CHAVE"
# O cookie é reemitido (renovando a validade no navegador) quando tem mais de um dia ou quando o token de renovação muda.
REEMITIR_COOKIE_APOS_SEGUNDOS = UM_DIA_SEGUNDOS
_CAMPOS = {"u": str, "e": str, "p": str, "r": str, "c": (int, float), "t": str}


class Lacre:
    def __init__(self, chave: str | None, relogio: Callable[[], float] = time):
        self._relogio = relogio
        self._fernet = None
        if chave:
            try:
                self._fernet = Fernet(chave.encode() if isinstance(chave, str) else chave)
            except ValueError:
                logger.error("%s inválida: precisa ser uma chave Fernet (32 bytes em base64). Sessão longa desligada.", VARIAVEL_CHAVE)

    @property
    def ativo(self) -> bool:
        return self._fernet is not None

    def selar(self, sessao) -> str:
        """Texto cifrado para o cookie `lembrar`. Só o que é preciso para refazer a sessão."""
        dados = {
            "u": sessao.usuario_id, "e": sessao.email, "p": sessao.papel,
            "r": sessao.refresh_token, "c": sessao.criada_em or self._relogio(), "t": sessao.csrf_token,
        }
        return self._fernet.encrypt_at_time(json.dumps(dados).encode(), int(self._relogio())).decode()

    def abrir(self, valor: str | None) -> dict | None:
        """Dados do cookie, ou None se ausente, adulterado, de outra chave, velho demais ou malformado."""
        if not self.ativo or not valor:
            return None
        agora = self._relogio()
        try:
            bruto = self._fernet.decrypt_at_time(valor.encode(), VIDA_MAXIMA_SEGUNDOS, int(agora))
            dados = json.loads(bruto)
        except (InvalidToken, ValueError, UnicodeError):
            return None
        if not isinstance(dados, dict) or any(not isinstance(dados.get(k), tipo) for k, tipo in _CAMPOS.items()):
            return None
        if not dados["r"] or not dados["u"] or sessao_vencida(dados["c"], agora, agora):
            return None
        return dados


def lacre_do_ambiente(relogio: Callable[[], float] = time) -> Lacre:
    return Lacre(os.getenv(VARIAVEL_CHAVE) or None, relogio)


def gravar_cookies(resposta, request_https: bool, sessao, lacre: Lacre, agora: float) -> None:
    """Grava `sessao` (e `lembrar`, se o recurso está ligado) com validade longa e marca quando foram emitidos."""
    comuns = {"httponly": True, "secure": request_https, "samesite": "lax", "path": "/"}
    resposta.set_cookie(COOKIE_SESSAO, sessao.id, max_age=INATIVIDADE_MAXIMA_SEGUNDOS, **comuns)
    if lacre.ativo:
        resposta.set_cookie(COOKIE_LEMBRAR, lacre.selar(sessao), max_age=INATIVIDADE_MAXIMA_SEGUNDOS, **comuns)
    sessao.cookie_emitido_em = agora
    sessao.cookie_pendente = False


def apagar_cookies(resposta) -> None:
    resposta.delete_cookie(COOKIE_SESSAO, path="/")
    resposta.delete_cookie(COOKIE_LEMBRAR, path="/")


class CookiesDaSessao(BaseHTTPMiddleware):
    """Reemite os cookies da sessão depois da resposta: quando o token de renovação mudou, a sessão foi refeita a partir
    do cookie `lembrar` ou o cookie tem mais de um dia (a validade no navegador anda junto com o uso)."""

    async def dispatch(self, request, call_next):
        resposta = await call_next(request)
        sessao = getattr(request.state, "sessao", None)
        if sessao is None:
            return resposta
        estado = request.app.state
        agora = estado.relogio()
        velho = agora - sessao.cookie_emitido_em > REEMITIR_COOKIE_APOS_SEGUNDOS
        if (sessao.cookie_pendente or velho) and estado.armazem.contem(sessao.id):
            gravar_cookies(resposta, request.url.scheme == "https", sessao, estado.lacre, agora)
        return resposta
