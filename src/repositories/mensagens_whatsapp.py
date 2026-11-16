"""RPCs do envio automático de WhatsApp (usuário de serviço ou administrador). Sem cache: o script lê sempre o estado atual."""

from datetime import date, datetime, timezone

from src.db import get_client


def dados(dia: date) -> dict:
    """Tudo o que as regras precisam para decidir o que enviar no `dia` (`rpc_whatsapp_dados`), com o grupo de cada cliente.

    O grupo vem de outra RPC (`rpc_whatsapp_grupos_clientes`) e entra em `clientes[].whatsapp_grupo_id`."""
    cliente = get_client()
    bruto = cliente.rpc("rpc_whatsapp_dados", {"p_dia": dia.isoformat()}).execute().data
    grupos = cliente.rpc("rpc_whatsapp_grupos_clientes").execute().data or {}
    for c in bruto["clientes"]:
        c["whatsapp_grupo_id"] = grupos.get(c["id"])
    return bruto


def gravar_grupos(grupos: list[dict]) -> int:
    """Substitui a lista de grupos da instância guardada no banco (`rpc_whatsapp_gravar_grupos`). Devolve quantos ficaram."""
    return get_client().rpc("rpc_whatsapp_gravar_grupos", {"payload": {"grupos": grupos}}).execute().data


def listar_grupos() -> list[dict]:
    """Grupos guardados (sessão do dono, pela RLS), por nome."""
    return get_client().table("whatsapp_grupos").select("*").order("nome").execute().data


def enfileirar(mensagens: list[dict]) -> dict:
    return get_client().rpc("rpc_whatsapp_enfileirar", {"payload": {"mensagens": mensagens}}).execute().data


def reservar(limite: int) -> list[dict]:
    return get_client().rpc("rpc_whatsapp_reservar", {"p_limite": limite}).execute().data


def registrar_resultado(mensagem_id: str, resultado: str, erro: str | None = None, evolution_id: str | None = None) -> dict:
    return get_client().rpc("rpc_whatsapp_registrar_resultado", {
        "p_id": mensagem_id, "p_resultado": resultado, "p_erro": erro, "p_evolution_id": evolution_id,
    }).execute().data


def registrar_rodada(estado: str, resumo: dict | None = None) -> None:
    """Grava o que a rodada viu (estado da instância e resumo) para o Dashboard avisar o dono."""
    get_client().rpc("rpc_whatsapp_registrar_rodada", {"p_estado": estado, "p_resumo": resumo}).execute()


# ---------------------------------------------------------------- telas do dono --
# (sessão do dono, pelas políticas de RLS; cada ação mexe em uma tabela só)

_TABELA = "mensagens_whatsapp"
_SELECAO = "*, clientes(nome), mensagens_whatsapp_itens(tipo)"


def listar_recentes(limite: int = 300, desde: datetime | None = None, cliente_id: str | None = None) -> list[dict]:
    consulta = get_client().table(_TABELA).select(_SELECAO).order("criado_em", desc=True).limit(limite)
    if desde is not None:
        consulta = consulta.gte("criado_em", desde.isoformat())
    if cliente_id is not None:
        consulta = consulta.eq("cliente_id", cliente_id)
    return consulta.execute().data


def cancelar(mensagem_id: str) -> list[dict]:
    """Cancela uma pendente ou que falhou. Lista vazia = ela já mudou de situação."""
    return (get_client().table(_TABELA)
            .update({"status": "cancelada", "erro": "Cancelada pelo dono.", "reservada_ate": None})
            .eq("id", mensagem_id).in_("status", ["pendente", "falhou"]).execute().data)


def reenviar(mensagem_id: str) -> list[dict]:
    """Devolve à fila uma mensagem que falhou (nova contagem de tentativas). Lista vazia = ela já mudou de situação."""
    return (get_client().table(_TABELA)
            .update({"status": "pendente", "tentativas": 0, "erro": None, "reservada_ate": None,
                     "enviar_apos": datetime.now(timezone.utc).isoformat()})
            .eq("id", mensagem_id).eq("status", "falhou").execute().data)
