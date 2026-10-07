"""Fronteira de escrita da página Manutenção."""

from src.services import manutencao


def registrar(dados: dict, chave_operacao: str):
    return manutencao.registrar_manutencao(**dados, chave_operacao=chave_operacao)
