"""Fronteira de escrita do Portal do Locatário."""

from src.services import portal_locatario


def registrar_troca_oleo(cliente_id, contrato, km_texto, foto, nota, multa):
    """Valida de novo, envia as duas imagens ao Storage e registra pela RPC (que confere o contrato e calcula a multa).

    `foto` e `nota`: (nome, conteúdo em bytes). Devolve {"excedeu", "multa_valor"}."""
    return portal_locatario.registrar_troca_oleo(cliente_id, contrato, km_texto, foto, nota, multa)


def alterar_senha(servico, access_token, nova):
    """Troca a senha do próprio usuário no Supabase Auth, com o token da sessão dele."""
    servico.alterar_senha(access_token, nova)
