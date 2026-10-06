"""Sessões do app web, guardadas na memória do processo.

O cookie leva só um identificador aleatório; os tokens do Supabase ficam aqui, no
servidor. Consequências assumidas (decisão 1 da Fase 1):
- reiniciar o processo (ou fazer deploy) encerra todas as sessões;
- o app precisa rodar com UM único worker, senão cada worker teria suas sessões.
"""

import secrets
from dataclasses import dataclass, field
from threading import Lock
from time import time
from typing import Callable

LIMITE_INATIVIDADE_SEGUNDOS = 1800
# Renova o access token um pouco antes de vencer, para a requisição não falhar no meio.
MARGEM_RENOVACAO_SEGUNDOS = 60


@dataclass
class Sessao:
    id: str
    usuario_id: str
    email: str
    papel: str
    access_token: str
    refresh_token: str
    expira_em: float
    ultima_atividade: float
    csrf_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    # Serializa a renovação dos tokens: o refresh token é de uso único e várias
    # requisições HTMX da mesma sessão podem chegar ao mesmo tempo.
    trava: Lock = field(default_factory=Lock, repr=False)
    cliente: object | None = field(default=None, repr=False)

    def access_token_vencendo(self, agora: float) -> bool:
        return self.expira_em - agora <= MARGEM_RENOVACAO_SEGUNDOS


class ArmazemSessoes:
    def __init__(
        self,
        limite_inatividade: int = LIMITE_INATIVIDADE_SEGUNDOS,
        relogio: Callable[[], float] = time,
    ):
        self._sessoes: dict[str, Sessao] = {}
        self._trava = Lock()
        self._limite = limite_inatividade
        self._relogio = relogio

    def criar(
        self,
        *,
        usuario_id: str,
        email: str,
        papel: str,
        access_token: str,
        refresh_token: str,
        expira_em: float,
    ) -> Sessao:
        """Abre uma sessão nova, com identificador novo (evita fixação de sessão)."""
        sessao = Sessao(
            id=secrets.token_urlsafe(32),
            usuario_id=usuario_id,
            email=email,
            papel=papel,
            access_token=access_token,
            refresh_token=refresh_token,
            expira_em=expira_em,
            ultima_atividade=self._relogio(),
        )
        with self._trava:
            self._limpar_expiradas_sem_trava()
            self._sessoes[sessao.id] = sessao
        return sessao

    def obter(self, sessao_id: str | None) -> Sessao | None:
        """Devolve a sessão válida e renova o prazo de inatividade; None se não há ou expirou."""
        if not sessao_id:
            return None
        agora = self._relogio()
        with self._trava:
            sessao = self._sessoes.get(sessao_id)
            if sessao is None:
                return None
            if agora - sessao.ultima_atividade > self._limite:
                del self._sessoes[sessao_id]
                return None
            sessao.ultima_atividade = agora
            return sessao

    def encerrar(self, sessao_id: str | None) -> Sessao | None:
        """Remove a sessão e a devolve (para o chamador revogar o token no Supabase)."""
        if not sessao_id:
            return None
        with self._trava:
            return self._sessoes.pop(sessao_id, None)

    def quantidade(self) -> int:
        with self._trava:
            return len(self._sessoes)

    def _limpar_expiradas_sem_trava(self) -> None:
        agora = self._relogio()
        vencidas = [
            id_
            for id_, s in self._sessoes.items()
            if agora - s.ultima_atividade > self._limite
        ]
        for id_ in vencidas:
            del self._sessoes[id_]
