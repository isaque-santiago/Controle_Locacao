"""Fronteira de escrita das telas web de Clientes."""

from src.services import clientes, pedidos_senha, portal_locatario


def criar_cliente(dados):
    return clientes.criar(dados)


def atualizar_cliente(cliente_id, dados):
    return clientes.atualizar(cliente_id, dados)


def criar_acesso_portal(cliente_id):
    """Devolve {"email", "senha"}; a senha só existe nesta resposta."""
    return portal_locatario.criar_acesso(cliente_id)


def redefinir_senha_portal(cliente_id):
    """Gera a senha nova e, só depois de dar certo, fecha o pedido de senha do locatário (se houver)."""
    credenciais = portal_locatario.redefinir_senha(cliente_id)
    pedidos_senha.atender(cliente_id)
    return credenciais


def remover_acesso_portal(cliente_id):
    """Remove o login e fecha o pedido de senha que sobrasse (sem login não há senha para gerar)."""
    portal_locatario.remover_acesso(cliente_id)
    pedidos_senha.atender(cliente_id)


def dispensar_pedido_senha(cliente_id):
    """O dono descarta o pedido de senha nova (por exemplo, quando não foi o locatário que pediu)."""
    pedidos_senha.dispensar(cliente_id)


def url_arquivo_troca(arquivo_path):
    return portal_locatario.url_arquivo(arquivo_path)
