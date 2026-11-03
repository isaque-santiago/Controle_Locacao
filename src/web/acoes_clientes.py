"""Fronteira de escrita das telas web de Clientes."""

from src.services import clientes, portal_locatario


def criar_cliente(dados):
    return clientes.criar(dados)


def atualizar_cliente(cliente_id, dados):
    return clientes.atualizar(cliente_id, dados)


def criar_acesso_portal(cliente_id):
    """Devolve {"email", "senha"}; a senha só existe nesta resposta."""
    return portal_locatario.criar_acesso(cliente_id)


def redefinir_senha_portal(cliente_id):
    return portal_locatario.redefinir_senha(cliente_id)


def remover_acesso_portal(cliente_id):
    portal_locatario.remover_acesso(cliente_id)


def url_arquivo_troca(arquivo_path):
    return portal_locatario.url_arquivo(arquivo_path)
