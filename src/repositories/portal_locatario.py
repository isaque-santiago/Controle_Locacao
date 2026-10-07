"""RPCs do portal do locatário (Fase 7) e upload/URL das fotos de troca de óleo.

O locatário não tem acesso direto às tabelas: lê e grava só por RPCs
SECURITY DEFINER, que o identificam por auth.uid(). O dono usa as RPCs de vínculo
e lê as trocas (e as fotos, por URL assinada) com a própria sessão.
"""

from pathlib import PurePath
from uuid import uuid4

from src.db import get_client
from src.repositories.consultas import invalida_cache, todos

BUCKET = "trocas_oleo"
FUNCAO_ACESSO = "criar-locatario"


def meu_papel():
    """'dono', 'locatario' ou None (usuário sem permissão)."""
    return get_client().rpc("rpc_meu_papel").execute().data


def dados_portal() -> dict:
    return get_client().rpc("rpc_portal_locatario").execute().data


@invalida_cache
def registrar_troca(payload: dict) -> dict:
    return (
        get_client()
        .rpc("rpc_registrar_troca_oleo_locatario", {"payload": payload})
        .execute()
        .data
    )


def enviar_arquivo(
    cliente_id: str, nome_arquivo: str, conteudo: bytes, content_type: str
) -> str:
    """Envia a imagem para a pasta do cliente no bucket privado; devolve o caminho.

    Sem upsert: o locatário só tem permissão de inserir, nunca de sobrescrever."""
    caminho = f"{cliente_id}/{uuid4().hex}{PurePath(nome_arquivo).suffix.lower()}"
    get_client().storage.from_(BUCKET).upload(
        caminho, conteudo, {"content-type": content_type, "upsert": "false"}
    )
    return caminho


def alterar_senha(nova_senha: str) -> None:
    """Troca a senha do usuário logado no Supabase Auth."""
    get_client().auth.update_user({"password": nova_senha})


# ---- Somente o dono ----------------------------------------------------------


def _jwt_do_dono(cliente) -> str:
    """JWT do usuário logado: o da sessão (Streamlit) ou o do cabeçalho do cliente por requisição (web)."""
    sessao = cliente.auth.get_session()
    if sessao is not None:
        return sessao.access_token
    autorizacao = cliente.options.headers.get("Authorization", "")
    if not autorizacao.startswith("Bearer "):
        raise ValueError("Sessão expirada. Entre novamente.")
    return autorizacao.removeprefix("Bearer ")


@invalida_cache
def gerenciar_acesso(acao: str, cliente_id: str) -> dict:
    """Chama a Edge Function criar-locatario (criar, redefinir ou remover o acesso).

    Só ela usa a service_role, dentro do Supabase; o app manda apenas o JWT do dono.
    A função responde sempre JSON: {"ok": true, ...} ou {"ok": false, "erro": "..."}."""
    cliente = get_client()
    return cliente.functions.invoke(
        FUNCAO_ACESSO,
        invoke_options={
            "headers": {"Authorization": f"Bearer {_jwt_do_dono(cliente)}"},
            "body": {"acao": acao, "cliente_id": cliente_id},
            "responseType": "json",
        },
    )


def listar_trocas(cliente_id: str):
    return todos("trocas_oleo", "criado_em", filtros={"cliente_id": cliente_id})


def url_assinada(arquivo_path: str, expira_em: int = 300) -> str:
    resposta = get_client().storage.from_(BUCKET).create_signed_url(arquivo_path, expira_em)
    return resposta.get("signedURL") or resposta.get("signedUrl")
