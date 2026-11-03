"""Fotos enviadas em formulários multipart (vistoria, assistente de contrato e "Adicionar fotos")."""

from starlette.datastructures import UploadFile

from src.domain import formulario_vistoria as formulario


def separar_formulario(enviado) -> tuple[dict, list]:
    """Divide o formulário em texto (`entrada`) e arquivos do campo `fotos` (os vazios, de quem não escolheu nada, saem)."""
    entrada = {chave: valor for chave, valor in enviado.items() if isinstance(valor, str)}
    fotos = [valor for chave, valor in enviado.multi_items()
             if chave == "fotos" and isinstance(valor, UploadFile) and valor.filename]
    return entrada, fotos


def resumo_fotos(fotos):
    """(nome, tamanho, primeiros bytes) de cada foto, sem ler o arquivo inteiro."""
    resumo = []
    for foto in fotos:
        cabecalho = foto.file.read(formulario.BYTES_DA_ASSINATURA)
        foto.file.seek(0)
        resumo.append((foto.filename, foto.size or 0, cabecalho))
    return resumo
