"""Fronteira de escrita da página Documentos."""

from pathlib import PurePath

from src.domain.formulario_documento import TIPOS_CONTEUDO
from src.services import documentos


def criar_documento(dados, chave_operacao):
    """Cria o documento; repetir a mesma `chave_operacao` devolve o já gravado em vez de criar outro."""
    return documentos.criar(dados, chave_operacao)


def atualizar_documento(documento_id, dados):
    return documentos.atualizar(documento_id, dados)


def anexar_comprovante(documento_id, moto_id, arquivo):
    """Envia o comprovante (objeto com `filename` e `file`); o tipo de conteúdo vem da extensão, não do navegador."""
    extensao = PurePath(arquivo.filename).suffix.lower()
    return documentos.anexar_comprovante(
        documento_id, moto_id, arquivo.filename, arquivo.file.read(), TIPOS_CONTEUDO.get(extensao, "application/octet-stream")
    )
