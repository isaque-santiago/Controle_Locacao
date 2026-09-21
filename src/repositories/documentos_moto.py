"""CRUD da tabela documentos_moto e comprovantes no bucket privado 'documentos'."""

from src.db import get_client

TABELA = "documentos_moto"
BUCKET = "documentos"


def listar_por_moto(moto_id: str):
    resposta = (
        get_client()
        .table(TABELA)
        .select("*")
        .eq("moto_id", moto_id)
        .order("vencimento")
        .execute()
    )
    return resposta.data


def listar_pendentes():
    resposta = (
        get_client()
        .table(TABELA)
        .select("*, moto:motos(placa, modelo)")
        .eq("regularizado", False)
        .order("vencimento")
        .execute()
    )
    return resposta.data


def obter(documento_id: str):
    resposta = (
        get_client().table(TABELA).select("*").eq("id", documento_id).maybe_single().execute()
    )
    return resposta.data if resposta else None


def criar(dados: dict):
    resposta = get_client().table(TABELA).insert(dados).execute()
    return resposta.data[0]


def atualizar(documento_id: str, dados: dict):
    resposta = get_client().table(TABELA).update(dados).eq("id", documento_id).execute()
    return resposta.data[0]


def upload_comprovante(
    moto_id: str, documento_id: str, nome_arquivo: str, conteudo: bytes, content_type: str
) -> str:
    """Envia o comprovante para o bucket privado; retorna o caminho gravado
    em documentos_moto.arquivo_path (o bucket não é público — acesso só por
    URL assinada, ver url_assinada)."""
    caminho = f"{moto_id}/{documento_id}/{nome_arquivo}"
    get_client().storage.from_(BUCKET).upload(
        caminho, conteudo, {"content-type": content_type, "upsert": "true"}
    )
    return caminho


def url_assinada(arquivo_path: str, expira_em: int = 300) -> str:
    resposta = get_client().storage.from_(BUCKET).create_signed_url(arquivo_path, expira_em)
    return resposta.get("signedURL") or resposta.get("signedUrl")
