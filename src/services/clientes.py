"""Orquestra cadastro de clientes (validação de CPF e contatos)."""

from postgrest.exceptions import APIError

from src.domain import arquivamento
from src.domain.arquivamento import Pendencias
from src.domain.validadores import validar_cpf, validar_telefone
from src.repositories import clientes, cobrancas, contratos

_CODIGO_VIOLACAO_UNICIDADE = "23505"


def _apenas_digitos_cpf(cpf: str) -> str:
    return "".join(caractere for caractere in cpf if caractere.isdigit())


def _validar_dados(dados: dict) -> None:
    if not dados.get("nome", "").strip():
        raise ValueError("Informe o nome do cliente.")
    if not validar_cpf(dados.get("cpf", "")):
        raise ValueError("CPF inválido.")
    for campo in ("telefone", "whatsapp"):
        valor = dados.get(campo)
        if valor and not validar_telefone(valor):
            raise ValueError(f"Telefone inválido no campo '{campo}'.")


def listar():
    return clientes.listar()


def obter(cliente_id: str):
    return clientes.obter(cliente_id)


def criar(dados: dict) -> dict:
    dados = dict(dados)
    _validar_dados(dados)
    dados["cpf"] = _apenas_digitos_cpf(dados["cpf"])

    try:
        return clientes.criar(dados)
    except APIError as erro:
        if erro.code == _CODIGO_VIOLACAO_UNICIDADE:
            raise ValueError("Já existe um cliente cadastrado com esse CPF.") from erro
        raise


def atualizar(cliente_id: str, dados: dict) -> dict:
    dados = dict(dados)
    if {"nome", "cpf", "telefone", "whatsapp"} & dados.keys():
        cliente_atual = obter(cliente_id)
        if cliente_atual is None:
            raise ValueError("Cliente não encontrado.")
        _validar_dados({**cliente_atual, **dados})
    if "cpf" in dados:
        dados["cpf"] = _apenas_digitos_cpf(dados["cpf"])

    try:
        return clientes.atualizar(cliente_id, dados)
    except APIError as erro:
        if erro.code == _CODIGO_VIOLACAO_UNICIDADE:
            raise ValueError("Já existe um cliente cadastrado com esse CPF.") from erro
        raise


def pendencias_para_arquivar(cliente_id: str) -> Pendencias:
    """O que impede arquivar o cliente (contrato ativo, cobrança em aberto, inclusive de contrato encerrado)."""
    return arquivamento.pendencias_do_cliente(cliente_id, contratos.listar(), cobrancas.listar())


def arquivar(cliente_id: str) -> dict:
    """Arquiva o ex-locatário se não houver pendências. O banco confere de novo na RPC."""
    cliente = clientes.obter(cliente_id)
    if cliente is None:
        raise ValueError("Cliente não encontrado.")
    if arquivamento.esta_arquivado(cliente):
        raise ValueError("Este cliente já está arquivado.")
    pendencias = pendencias_para_arquivar(cliente_id)
    if not pendencias.pode_arquivar:
        raise ValueError(arquivamento.texto_recusa(pendencias, "o cliente"))
    return clientes.arquivar_via_rpc(cliente_id)


def desarquivar(cliente_id: str) -> dict:
    return clientes.desarquivar_via_rpc(cliente_id)
