"""Fronteira de escrita das telas de WhatsApp."""

from src.services import whatsapp_painel


def cancelar(mensagem_id: str) -> None:
    whatsapp_painel.cancelar(mensagem_id)


def reenviar(mensagem_id: str) -> None:
    whatsapp_painel.reenviar(mensagem_id)


def bloquear(cliente_id: str, motivo: str) -> None:
    whatsapp_painel.bloquear(cliente_id, motivo)


def desbloquear(cliente_id: str) -> None:
    whatsapp_painel.desbloquear(cliente_id)


def atualizar_controles(dados: dict) -> dict:
    return whatsapp_painel.atualizar_controles(dados)
