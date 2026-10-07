"""Fronteira de escrita da página Manutenção."""

from src.services import manutencao


def registrar(dados: dict, chave_operacao: str):
    return manutencao.registrar_manutencao(**dados, chave_operacao=chave_operacao)


def finalizar(manutencao_id, status, data, km):
    return manutencao.finalizar(manutencao_id, status, data, km)


def criar_item(dados):
    return manutencao.criar_item_catalogo(dados)


def atualizar_item(item_id, dados):
    return manutencao.atualizar_item_catalogo(item_id, dados)
