"""Pedidos de senha nova do portal (`pedidos_senha_portal`), do lado do dono.

O locatário pede sem login pela RPC `rpc_portal_pedir_redefinicao` (ver `services/autenticacao.py`); o dono lê e fecha os pedidos
pela própria sessão (política `dono_total`). No máximo um pedido aberto por cliente."""

from datetime import datetime, timezone

from src.db import get_client

TABELA = "pedidos_senha_portal"


def listar_abertos() -> list[dict]:
    return get_client().table(TABELA).select("*, clientes(nome)").eq("status", "aberto").order("pedido_em").execute().data


def aberto_do_cliente(cliente_id: str) -> dict | None:
    resposta = get_client().table(TABELA).select("*").eq("cliente_id", cliente_id).eq("status", "aberto").limit(1).execute()
    return resposta.data[0] if resposta.data else None


def fechar(cliente_id: str, status: str) -> list[dict]:
    """Fecha o pedido aberto do cliente como `atendido` ou `dispensado`. Lista vazia = não havia pedido aberto."""
    return (get_client().table(TABELA)
            .update({"status": status, "fechado_em": datetime.now(timezone.utc).isoformat()})
            .eq("cliente_id", cliente_id).eq("status", "aberto").execute().data)
