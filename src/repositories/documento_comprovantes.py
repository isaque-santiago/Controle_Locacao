"""Comprovantes de documento enviados pelos locatários (`documento_comprovantes`), do lado do dono.

O locatário envia por RPC (`repositories/portal_locatario.py`); o dono lê pela própria sessão (política `dono_total`),
aceita pela RPC `rpc_aceitar_comprovante_documento` (regulariza o documento e fecha o envio numa transação) e recusa
atualizando uma tabela só."""

from datetime import date, datetime, timezone

from src.db import get_client
from src.repositories.consultas import invalida_cache

TABELA = "documento_comprovantes"
_SELECAO = "*, clientes(nome), documentos_moto(tipo, descricao, ano_referencia, moto_id, motos(placa))"


def listar_aguardando() -> list[dict]:
    return get_client().table(TABELA).select(_SELECAO).eq("status", "enviado").order("enviado_em").execute().data


def aguardando_do_documento(documento_id: str) -> dict | None:
    resposta = (get_client().table(TABELA).select(_SELECAO).eq("documento_id", documento_id).eq("status", "enviado")
                .limit(1).execute())
    return resposta.data[0] if resposta.data else None


def historico_do_documento(documento_id: str) -> list[dict]:
    """Todos os envios do documento, o mais recente primeiro (aguardando, aceitos e recusados)."""
    return (get_client().table(TABELA).select("*, clientes(nome)").eq("documento_id", documento_id)
            .order("enviado_em", desc=True).execute().data)


@invalida_cache
def aceitar(envio_id: str, data: date) -> dict:
    return get_client().rpc("rpc_aceitar_comprovante_documento", {"p_envio": envio_id, "p_data": data.isoformat()}).execute().data


@invalida_cache
def recusar(envio_id: str, motivo: str) -> list[dict]:
    """Recusa um envio que ainda aguarda. Lista vazia = ele já foi conferido."""
    return (get_client().table(TABELA)
            .update({"status": "recusado", "motivo_recusa": motivo, "conferido_em": datetime.now(timezone.utc).isoformat()})
            .eq("id", envio_id).eq("status", "enviado").execute().data)
