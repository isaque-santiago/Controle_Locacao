"""CRUD de vistoria_fotos e upload de fotos no bucket privado 'vistorias'."""

from pathlib import PurePath
from uuid import uuid4
from src.db import get_client

TABELA = "vistoria_fotos"
BUCKET = "vistorias"


def listar_por_vistoria(vistoria_id: str):
    resposta = (
        get_client().table(TABELA).select("*").eq("vistoria_id", vistoria_id).execute()
    )
    return resposta.data


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


def upload_foto(
    vistoria_id: str, nome_arquivo: str, conteudo: bytes, content_type: str
) -> str:
    """Envia a foto para o bucket privado; retorna o caminho gravado em
    vistoria_fotos.storage_path (acesso só por URL assinada)."""
    nome_arquivo = uuid4().hex + PurePath(nome_arquivo).suffix.lower()
    caminho = f"{vistoria_id}/{nome_arquivo}"
    get_client().storage.from_(BUCKET).upload(
        caminho, conteudo, {"content-type": content_type, "upsert": "true"}
    )
    return caminho


def url_assinada(arquivo_path: str, expira_em: int = 300) -> str:
    resposta = (
        get_client().storage.from_(BUCKET).create_signed_url(arquivo_path, expira_em)
    )
    return resposta.get("signedURL") or resposta.get("signedUrl")
