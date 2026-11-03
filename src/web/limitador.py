"""Limite de tentativas de login, em memória (por IP e por identificador)."""

from collections import deque
from threading import Lock
from time import time
from typing import Callable


class LimitadorTentativas:
    """Bloqueia uma chave após `maximo` falhas dentro de `janela` segundos.

    A chave volta a valer quando as falhas mais antigas saem da janela; um login bem
    sucedido zera a chave do identificador (não a do IP, que pode ser compartilhado)."""

    def __init__(
        self,
        maximo: int,
        janela: int = 900,
        relogio: Callable[[], float] = time,
    ):
        self._maximo = maximo
        self._janela = janela
        self._relogio = relogio
        self._falhas: dict[str, deque[float]] = {}
        self._trava = Lock()

    def _podar(self, chave: str, agora: float) -> deque[float]:
        falhas = self._falhas.setdefault(chave, deque())
        while falhas and agora - falhas[0] >= self._janela:
            falhas.popleft()
        if not falhas:
            self._falhas.pop(chave, None)
        return falhas

    def segundos_de_bloqueio(self, chave: str) -> int:
        """0 se a chave pode tentar; senão, quantos segundos faltam para liberar."""
        agora = self._relogio()
        with self._trava:
            falhas = self._podar(chave, agora)
            if len(falhas) < self._maximo:
                return 0
            return max(1, int(falhas[0] + self._janela - agora) + 1)

    def registrar_falha(self, chave: str) -> None:
        agora = self._relogio()
        with self._trava:
            self._podar(chave, agora)
            self._falhas.setdefault(chave, deque()).append(agora)

    def limpar(self, chave: str) -> None:
        with self._trava:
            self._falhas.pop(chave, None)
