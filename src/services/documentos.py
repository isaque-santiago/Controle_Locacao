"""Orquestra cadastro, comprovantes e regularização de documentos da moto."""

from datetime import date

from src.domain.arquivos import validar_arquivo
from src.domain.documentos import sugerir_proximo_documento
from src.repositories import documentos_moto

_EXTENSOES_PERMITIDAS = (".pdf", ".png", ".jpg", ".jpeg")


def listar_por_moto(moto_id: str):
    return documentos_moto.listar_por_moto(moto_id)


def listar_todos():
    return documentos_moto.listar_todos()


def listar_pendentes():
    return documentos_moto.listar_pendentes()


def obter(documento_id: str):
    return documentos_moto.obter(documento_id)


def criar(dados: dict) -> dict:
    return documentos_moto.criar(dados)


def atualizar(documento_id: str, dados: dict) -> dict:
    return documentos_moto.atualizar(documento_id, dados)


def anexar_comprovante(
    documento_id: str, moto_id: str, nome_arquivo: str, conteudo: bytes, content_type: str
) -> dict:
    validar_arquivo(nome_arquivo, conteudo, _EXTENSOES_PERMITIDAS)
    caminho = documentos_moto.upload_comprovante(
        moto_id, documento_id, nome_arquivo, conteudo, content_type
    )
    return documentos_moto.atualizar(documento_id, {"arquivo_path": caminho})


def url_comprovante(arquivo_path: str, expira_em: int = 300) -> str:
    """URL assinada de curta duração — o bucket 'documentos' é privado."""
    return documentos_moto.url_assinada(arquivo_path, expira_em)


def regularizar(documento_id: str, data_regularizacao: date) -> dict:
    """Marca o documento como regularizado e, se for de renovação anual,
    devolve a sugestão do documento do ano seguinte (a tela decide se cria)."""
    documento = documentos_moto.atualizar(
        documento_id,
        {"regularizado": True, "data_regularizacao": data_regularizacao.isoformat()},
    )
    sugestao = sugerir_proximo_documento(documento["tipo"], documento.get("ano_referencia"))
    return {"documento": documento, "sugestao_proximo": sugestao}
