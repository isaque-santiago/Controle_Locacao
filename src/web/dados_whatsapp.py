"""Fronteira de leitura das telas de WhatsApp. Os testes das rotas trocam este serviço por dados fictícios."""

from src.domain import whatsapp_painel as regras
from src.services import whatsapp_painel


def mensagens(filtro: str) -> dict:
    """Mensagens recentes: a lista do filtro e quantas há em cada filtro."""
    todas = whatsapp_painel.listar_recentes()
    return {"itens": regras.filtrar(todas, filtro), "contagem": regras.contar_por_filtro(todas)}


def do_cliente(cliente_id: str) -> list[dict]:
    return whatsapp_painel.listar_do_cliente(cliente_id)
