"""RPCs do envio automático de WhatsApp (usuário de serviço ou administrador). Sem cache: o script lê sempre o estado atual."""

from datetime import date

from src.db import get_client


def dados(dia: date) -> dict:
    """Tudo o que as regras precisam para decidir o que enviar no `dia` (`rpc_whatsapp_dados`)."""
    return get_client().rpc("rpc_whatsapp_dados", {"p_dia": dia.isoformat()}).execute().data


def enfileirar(mensagens: list[dict]) -> dict:
    return get_client().rpc("rpc_whatsapp_enfileirar", {"payload": {"mensagens": mensagens}}).execute().data


def reservar(limite: int) -> list[dict]:
    return get_client().rpc("rpc_whatsapp_reservar", {"p_limite": limite}).execute().data


def registrar_resultado(mensagem_id: str, resultado: str, erro: str | None = None, evolution_id: str | None = None) -> dict:
    return get_client().rpc("rpc_whatsapp_registrar_resultado", {
        "p_id": mensagem_id, "p_resultado": resultado, "p_erro": erro, "p_evolution_id": evolution_id,
    }).execute().data
