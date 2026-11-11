"""Orquestra cadastro, comprovantes e regularização de documentos da moto."""

import logging
from datetime import date

from src.domain.arquivos import validar_arquivo
from src.domain.comprovante_documento import alertas_de_comprovantes as _alertas_de_comprovantes, nome_do_documento
from src.domain.privacidade_imagem import remover_dados_pessoais
from src.domain.documentos import sugerir_proximo_documento
from postgrest.exceptions import APIError

from src.repositories import documento_comprovantes, documentos_moto

_EXTENSOES_PERMITIDAS = (".pdf", ".png", ".jpg", ".jpeg")

log = logging.getLogger(__name__)


def listar_por_moto(moto_id: str):
    return documentos_moto.listar_por_moto(moto_id)


def listar_todos():
    return documentos_moto.listar_todos()


def listar_pendentes():
    return documentos_moto.listar_pendentes()


def obter(documento_id: str):
    return documentos_moto.obter(documento_id)


def criar(dados: dict, chave_operacao=None) -> dict:
    return documentos_moto.criar(dados, chave_operacao)


def atualizar(documento_id: str, dados: dict) -> dict:
    return documentos_moto.atualizar(documento_id, dados)


def anexar_comprovante(
    documento_id: str, moto_id: str, nome_arquivo: str, conteudo: bytes, content_type: str
) -> dict:
    validar_arquivo(nome_arquivo, conteudo, _EXTENSOES_PERMITIDAS)
    conteudo = remover_dados_pessoais(nome_arquivo, conteudo)
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


# ---------------------------------------------- comprovantes enviados pelo locatário --

_CODIGO_REGRA_DE_NEGOCIO = "P0001"  # raise exception ... nas RPCs
_JA_CONFERIDO = "Este comprovante já foi conferido. Atualize a página."


def comprovantes_aguardando() -> list[dict]:
    return documento_comprovantes.listar_aguardando()


def comprovante_aguardando(documento_id: str) -> dict | None:
    return documento_comprovantes.aguardando_do_documento(documento_id)


def historico_de_comprovantes(documento_id: str) -> list[dict]:
    return documento_comprovantes.historico_do_documento(documento_id)


def aceitar_comprovante(envio_id: str, data_regularizacao: date) -> dict:
    """Regulariza o documento com o arquivo do locatário (uma transação no banco). Devolve também a sugestão do ano seguinte."""
    try:
        resultado = documento_comprovantes.aceitar(envio_id, data_regularizacao)
    except APIError as erro:
        if erro.code == _CODIGO_REGRA_DE_NEGOCIO:
            raise ValueError(erro.message) from erro
        raise
    documento = documentos_moto.obter(resultado["documento_id"])
    return {"documento": documento, "sugestao_proximo": sugerir_proximo_documento(documento["tipo"], documento.get("ano_referencia"))}


def recusar_comprovante(envio_id: str, motivo: str) -> None:
    if not documento_comprovantes.recusar(envio_id, motivo):
        raise ValueError(_JA_CONFERIDO)


def alertas_de_comprovantes() -> list:
    """Item do Dashboard «Comprovante a conferir». Se a leitura falhar (migration ainda não aplicada), o Dashboard segue sem ele."""
    try:
        envios = documento_comprovantes.listar_aguardando()
    except Exception:
        log.exception("Não foi possível ler os comprovantes aguardando conferência para o Dashboard.")
        return []
    itens = []
    for e in envios:
        d = e.get("documentos_moto") or {}
        placa = (d.get("motos") or {}).get("placa")
        nome = nome_do_documento(d.get("tipo", "outro"), d.get("descricao"), d.get("ano_referencia"))
        itens.append({"cliente": (e.get("clientes") or {}).get("nome"), "documento": f"{nome} · {placa}" if placa else nome})
    return _alertas_de_comprovantes(itens)

