"""Pedidos de senha nova do portal, do lado do dono: alerta no Dashboard, aviso na ficha e fechamento do pedido."""

import logging

from src.domain.pedido_senha import alertas_de_pedidos
from src.repositories import pedidos_senha

log = logging.getLogger(__name__)


def alertas() -> list:
    """Item do Dashboard «Nova senha do portal pedida». Se a leitura falhar (migration ainda não aplicada), o Dashboard segue sem ele."""
    try:
        abertos = pedidos_senha.listar_abertos()
    except Exception:
        log.exception("Não foi possível ler os pedidos de senha nova para o Dashboard.")
        return []
    return alertas_de_pedidos([{"cliente": (p.get("clientes") or {}).get("nome")} for p in abertos])


def aberto_do_cliente(cliente_id: str) -> dict | None:
    """Pedido aguardando o dono para a ficha do cliente; `None` se não há, ou se a leitura falhar (a ficha não depende dele)."""
    try:
        return pedidos_senha.aberto_do_cliente(cliente_id)
    except Exception:
        log.exception("Não foi possível ler o pedido de senha nova do cliente.")
        return None


def dispensar(cliente_id: str) -> None:
    """O dono descarta o pedido (não vai gerar senha nova). Uma falha sobe para a tela, que avisa o dono."""
    pedidos_senha.fechar(cliente_id, "dispensado")


def atender(cliente_id: str) -> None:
    """Fecha o pedido depois de o dono gerar a senha nova (ou de remover o acesso). A senha já foi trocada: uma falha aqui não
    pode esconder isso do dono, então só vai para o log (o pedido fica aberto até ele dispensá-lo)."""
    try:
        pedidos_senha.fechar(cliente_id, "atendido")
    except Exception:
        log.exception("Não foi possível fechar o pedido de senha nova do cliente.")
