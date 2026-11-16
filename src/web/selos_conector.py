"""Tokens do conector do claude.ai, sem estado: cada um é um texto cifrado e assinado (Fernet) com a chave `CONECTOR_CHAVE`.

Etapa 1 (viabilidade) da seção 24 do plano. Sem banco, nada fica gravado: o client_id, o código de autorização, o token de acesso
e o de renovação carregam os próprios dados e a validade. Limitações assumidas, resolvidas na etapa 2 com tokens guardados (só o
hash) numa tabela do dono:
- não dá para revogar um token isolado; **trocar `CONECTOR_CHAVE` revoga tudo**;
- o uso único do código e do token de renovação vale só enquanto o processo vive (um deploy esquece os já usados)."""

import json
import logging
import os
import secrets
from threading import Lock
from time import time
from typing import Callable

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

VARIAVEL_CHAVE = "CONECTOR_CHAVE"
VARIAVEL_URL = "CONECTOR_URL_BASE"
VARIAVEL_LOOPBACK = "CONECTOR_PERMITE_LOOPBACK"

VALIDADE_CLIENTE = 10 * 365 * 86400
VALIDADE_CODIGO = 120
VALIDADE_ACESSO = 3600
VALIDADE_RENOVACAO = 90 * 86400


class Conector:
    """Configuração e selos do conector. Sem `chave`, o conector fica desligado (todas as rotas respondem 404)."""

    def __init__(self, chave: str | None, relogio: Callable[[], float] = time, url_base: str | None = None, permitir_loopback: bool = False):
        self._relogio = relogio
        self._fernet = None
        if chave:
            try:
                self._fernet = Fernet(chave.encode() if isinstance(chave, str) else chave)
            except ValueError:
                logger.error("%s inválida: precisa ser uma chave Fernet (32 bytes em base64). Conector desligado.", VARIAVEL_CHAVE)
        self.url_base = (url_base or "").rstrip("/")
        self.permitir_loopback = permitir_loopback
        self._usados: dict[str, float] = {}
        self._trava = Lock()

    @property
    def ativo(self) -> bool:
        return self._fernet is not None

    def agora(self) -> float:
        return self._relogio()

    def selar(self, tipo: str, dados: dict, validade: float) -> str:
        carga = {**dados, "t": tipo, "e": self._relogio() + validade, "j": secrets.token_urlsafe(12)}
        return self._fernet.encrypt_at_time(json.dumps(carga).encode(), int(self._relogio())).decode()

    def abrir(self, tipo: str, valor: str | None) -> dict | None:
        """Dados do selo do `tipo` pedido, ou None (ausente, adulterado, de outra chave, de outro tipo ou vencido)."""
        if not self.ativo or not valor or len(valor) > 4096:
            return None
        try:
            carga = json.loads(self._fernet.decrypt_at_time(valor.encode(), 10**10, int(self._relogio())))
        except (InvalidToken, ValueError, UnicodeError):
            return None
        if not isinstance(carga, dict) or carga.get("t") != tipo or not isinstance(carga.get("e"), (int, float)):
            return None
        return carga if carga["e"] > self._relogio() else None

    def consumir(self, carga: dict) -> bool:
        """Marca o selo como usado; False se já tinha sido (código ou token de renovação não valem duas vezes)."""
        agora = self._relogio()
        with self._trava:
            self._usados = {j: e for j, e in self._usados.items() if e > agora}
            if carga["j"] in self._usados:
                return False
            self._usados[carga["j"]] = carga["e"]
            return True


def conector_do_ambiente(relogio: Callable[[], float] = time) -> Conector:
    return Conector(
        os.getenv(VARIAVEL_CHAVE) or None,
        relogio,
        os.getenv(VARIAVEL_URL) or None,
        os.getenv(VARIAVEL_LOOPBACK, "").lower() in ("1", "true", "sim"),
    )
