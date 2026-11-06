"""O dono acompanhando o envio de WhatsApp: mensagens, bloqueio por cliente e controles (seção 20 do plano)."""

import logging
from datetime import datetime, timedelta, timezone

from src.domain.whatsapp_painel import DIAS_DE_PROBLEMA, achatar, alertas_whatsapp
from src.repositories import clientes as repo_clientes
from src.repositories import configuracoes as repo_configuracoes
from src.repositories import mensagens_whatsapp as repo

log = logging.getLogger("locacao.whatsapp")

_CAMPOS_DA_CONFIGURACAO = {"whatsapp_ativo", "whatsapp_modo_teste", "whatsapp_numero_teste", "whatsapp_max_repeticoes"}
_MUDOU = "Esta mensagem mudou de situação. Atualize a página para ver como ela está."


def listar_recentes(limite: int = 300) -> list[dict]:
    return [achatar(r) for r in repo.listar_recentes(limite)]


def listar_do_cliente(cliente_id: str, limite: int = 30) -> list[dict]:
    return [achatar(r) for r in repo.listar_recentes(limite, cliente_id=cliente_id)]


def cancelar(mensagem_id: str) -> None:
    if not repo.cancelar(mensagem_id):
        raise ValueError(_MUDOU)


def reenviar(mensagem_id: str) -> None:
    if not repo.reenviar(mensagem_id):
        raise ValueError(_MUDOU)


def bloquear(cliente_id: str, motivo: str) -> dict:
    return repo_clientes.atualizar(cliente_id, {
        "nao_enviar_whatsapp": True, "motivo_bloqueio_whatsapp": motivo,
        "bloqueio_whatsapp_em": datetime.now(timezone.utc).isoformat(),
    })


def desbloquear(cliente_id: str) -> dict:
    return repo_clientes.atualizar(cliente_id, {
        "nao_enviar_whatsapp": False, "motivo_bloqueio_whatsapp": None, "bloqueio_whatsapp_em": None,
    })


def atualizar_controles(dados: dict) -> dict:
    """Grava só os controles do envio (a validação é do formulário em `src/domain`)."""
    desconhecidos = set(dados) - _CAMPOS_DA_CONFIGURACAO
    if desconhecidos:
        raise ValueError("Campo não permitido: " + ", ".join(sorted(desconhecidos)))
    return repo_configuracoes.atualizar(dados)


def alertas(config: dict, agora: datetime | None = None) -> list:
    """Alertas do Dashboard. Se o banco ainda não tem as tabelas (migration não aplicada), o Dashboard segue sem eles."""
    agora = agora or datetime.now(timezone.utc)
    if not config.get("whatsapp_ativo"):
        return []
    try:
        desde = agora - timedelta(days=DIAS_DE_PROBLEMA)
        mensagens = [achatar(r) for r in repo.listar_recentes(500, desde=desde)]
    except Exception:
        log.exception("Não foi possível ler as mensagens de WhatsApp para os alertas.")
        return []
    return alertas_whatsapp(config, mensagens, agora)
