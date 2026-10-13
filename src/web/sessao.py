"""Sessões do app web, guardadas na memória do processo.

O cookie leva só um identificador aleatório; os tokens do Supabase ficam aqui, no
servidor. Consequências assumidas (decisão 1 da Fase 1):
- reiniciar o processo (ou fazer deploy) encerra todas as sessões;
- o app precisa rodar com UM único worker, senão cada worker teria suas sessões.

Só em DESENVOLVIMENTO o armazém pode espelhar as sessões num arquivo local (`arquivo=`), para a recarga automática do
servidor, a cada edição de `.py`, não derrubar o login. Em produção o arquivo nunca é configurado e nada vai a disco.
"""

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import time
from typing import Callable

logger = logging.getLogger(__name__)

LIMITE_INATIVIDADE_SEGUNDOS = 1800
# Vida máxima de uma sessão, mesmo com uso contínuo: obriga a entrar de novo e limita o estrago de um cookie roubado.
LIMITE_VIDA_SEGUNDOS = 12 * 3600
# A atividade (prazo de inatividade) só é regravada no arquivo de tempos em tempos; o resto é gravado na hora.
INTERVALO_SALVAR_ATIVIDADE_SEGUNDOS = 30
# O que vai para o arquivo: o suficiente para a sessão continuar valendo. O cliente Supabase é refeito a partir do token.
CAMPOS_PERSISTIDOS = (
    "id", "usuario_id", "email", "papel", "access_token", "refresh_token", "expira_em", "ultima_atividade", "csrf_token",
)
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
    criada_em: float = 0.0  # 0 = desconhecida (arquivo de desenvolvimento antigo): só vale a inatividade
    # Serializa a renovação dos tokens: o refresh token é de uso único e várias
    # requisições HTMX da mesma sessão podem chegar ao mesmo tempo.
    trava: Lock = field(default_factory=Lock, repr=False)
    cliente: object | None = field(default=None, repr=False)
    # Confirmações a mostrar na próxima página (uma só vez), como "Moto cadastrada."
    avisos: list = field(default_factory=list, repr=False)
    # Rascunho do assistente de novo contrato (cliente, moto, condições e textos digitados); some ao concluir.
    rascunho_contrato: dict = field(default_factory=dict, repr=False)

    def access_token_vencendo(self, agora: float) -> bool:
        return self.expira_em - agora <= MARGEM_RENOVACAO_SEGUNDOS


class ArmazemSessoes:
    def __init__(
        self,
        limite_inatividade: int = LIMITE_INATIVIDADE_SEGUNDOS,
        relogio: Callable[[], float] = time,
        arquivo: Path | str | None = None,
    ):
        self._sessoes: dict[str, Sessao] = {}
        self._trava = Lock()
        self._limite = limite_inatividade
        self._relogio = relogio
        self._arquivo = Path(arquivo) if arquivo else None
        self._ultimo_salvamento = 0.0
        if self._arquivo:
            self._carregar()

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
            criada_em=self._relogio(),
        )
        with self._trava:
            self._limpar_expiradas_sem_trava()
            self._sessoes[sessao.id] = sessao
            self._salvar_sem_trava()
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
            if self._vencida(sessao, agora):
                del self._sessoes[sessao_id]
                return None
            sessao.ultima_atividade = agora
            if agora - self._ultimo_salvamento >= INTERVALO_SALVAR_ATIVIDADE_SEGUNDOS:
                self._salvar_sem_trava()
            return sessao

    def encerrar(self, sessao_id: str | None) -> Sessao | None:
        """Remove a sessão e a devolve (para o chamador revogar o token no Supabase)."""
        if not sessao_id:
            return None
        with self._trava:
            sessao = self._sessoes.pop(sessao_id, None)
            self._salvar_sem_trava()
            return sessao

    def salvar(self) -> None:
        """Grava as sessões no arquivo (sem efeito sem arquivo). Chamado quando os tokens são renovados: o refresh
        token é de uso único, e perder o novo faria o login cair no próximo reinício."""
        with self._trava:
            self._salvar_sem_trava()

    def quantidade(self) -> int:
        with self._trava:
            return len(self._sessoes)

    def _vencida(self, sessao: Sessao, agora: float) -> bool:
        """Inativa por tempo demais ou mais velha que o limite de vida."""
        if agora - sessao.ultima_atividade > self._limite:
            return True
        return bool(sessao.criada_em) and agora - sessao.criada_em > LIMITE_VIDA_SEGUNDOS

    def _limpar_expiradas_sem_trava(self) -> None:
        agora = self._relogio()
        vencidas = [
            id_
            for id_, s in self._sessoes.items()
            if self._vencida(s, agora)
        ]
        for id_ in vencidas:
            del self._sessoes[id_]

    # ---- espelho em arquivo (só em desenvolvimento) ----

    def _salvar_sem_trava(self) -> None:
        if not self._arquivo:
            return
        self._ultimo_salvamento = self._relogio()
        dados = [
            {**{campo: getattr(s, campo) for campo in CAMPOS_PERSISTIDOS}, "criada_em": s.criada_em}
            for s in self._sessoes.values()
        ]
        temporario = self._arquivo.with_name(self._arquivo.name + ".tmp")
        try:
            temporario.write_text(json.dumps(dados), encoding="utf-8")
            try:
                os.chmod(temporario, 0o600)
            except OSError:
                pass
            os.replace(temporario, self._arquivo)
        except OSError:
            logger.warning("Não foi possível gravar o arquivo de sessões de desenvolvimento.", exc_info=True)

    def _carregar(self) -> None:
        """Lê as sessões ainda dentro do prazo de inatividade. Arquivo ausente ou ilegível vale como "sem sessões"."""
        try:
            dados = json.loads(self._arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        agora = self._relogio()
        for item in dados if isinstance(dados, list) else []:
            try:
                sessao = Sessao(**{campo: item[campo] for campo in CAMPOS_PERSISTIDOS})
            except (KeyError, TypeError):
                continue
            sessao.criada_em = float(item.get("criada_em") or 0.0)
            if not self._vencida(sessao, agora):
                self._sessoes[sessao.id] = sessao
