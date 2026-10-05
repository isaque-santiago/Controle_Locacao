"""Classificação de falhas para a tela (Plano de melhorias, Etapa 7).

Funções puras: recebem a exceção (ou só seus atributos) e devolvem a categoria e o texto
que a interface mostra. A interface decide a aparência e a ação (tentar novamente, entrar
de novo); aqui só se decide *o que aconteceu*. Sem importar Streamlit nem postgrest: a
exceção é lida por atributos (`code`, `message`, `status`) e pelo nome das classes.
"""

from collections import namedtuple

VALIDACAO = "validacao"
SESSAO_EXPIRADA = "sessao_expirada"
SEM_PERMISSAO = "sem_permissao"
INDISPONIVEL = "indisponivel"
CONFLITO = "conflito"
CONFIGURACAO = "configuracao"
DESCONHECIDO = "desconhecido"

# `recuperavel`: tentar de novo (a mesma ação, sem mudar nada) pode funcionar.
Falha = namedtuple("Falha", "categoria mensagem recuperavel")

_MENSAGENS_POR_CODIGO = {
    "23505": (CONFLITO, "Este registro já existe. Atualize a lista antes de tentar novamente."),
    "23514": (VALIDACAO, "Confira datas, valores e situação do cadastro."),
    "23503": (CONFLITO, "Há registros vinculados ou uma referência deixou de existir. Atualize a página."),
    "PGRST202": (CONFIGURACAO, "Aplique as migrations mais recentes no banco. Consulte o guia de instalação."),
}

_CODIGOS_SESSAO = {"PGRST301", "PGRST302"}
_CODIGOS_PERMISSAO = {"42501", "PGRST303"}
_STATUS_SESSAO = {401}
_STATUS_PERMISSAO = {403}
_STATUS_INDISPONIVEL = {408, 429, 500, 502, 503, 504}

# Classes de rede/tempo esgotado das bibliotecas HTTP, reconhecidas pelo nome para o
# domínio não depender delas (httpx, httpcore, requests, urllib3).
_NOMES_REDE = {
    "ConnectError",
    "ConnectTimeout",
    "ReadTimeout",
    "WriteTimeout",
    "PoolTimeout",
    "TimeoutException",
    "NetworkError",
    "ReadError",
    "WriteError",
    "CloseError",
    "RemoteProtocolError",
    "ProxyError",
    "ConnectionError",
    "ConnectionResetError",
    "TimeoutError",
    "gaierror",
}
_NOMES_SESSAO = {"AuthSessionMissingError", "AuthRetryableError", "AuthInvalidJwtError"}

MENSAGEM_SESSAO = "Sua sessão expirou. Entre novamente para continuar; o que já foi salvo não se perde."
MENSAGEM_PERMISSAO = "Seu acesso não permite esta operação. Peça ao proprietário para liberar ou entre com outra conta."
MENSAGEM_INDISPONIVEL = (
    "Não foi possível falar com o serviço agora. Verifique a conexão e tente novamente."
)
MENSAGEM_SERVICO = (
    "Não foi possível acessar o serviço. Verifique a conexão e a configuração do Supabase e tente novamente."
)
MENSAGEM_DESCONHECIDO = "Não foi possível concluir a operação. Confira os dados e atualize a página."


def _nomes_da_classe(erro):
    return {tipo.__name__ for tipo in type(erro).__mro__}


def _numero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _texto(erro):
    mensagem = getattr(erro, "message", None)
    return str(mensagem if mensagem else erro).lower()


def classificar_erro(erro):
    """Categoria, mensagem e se vale tentar de novo, a partir de uma exceção.

    - `ValueError`: validação do domínio; a mensagem já é para o usuário e vem inalterada.
    - Sessão expirada (JWT vencido, 401, sessão ausente): pede novo login; repetir não adianta.
    - Falta de permissão (RLS 42501, 403): repetir não adianta.
    - Indisponibilidade (rede, tempo esgotado, 5xx, 429): repetir pode funcionar.
    - Demais erros do banco: conflito, validação do banco ou configuração, com texto próprio."""
    if isinstance(erro, ValueError):
        return Falha(VALIDACAO, str(erro), False)

    codigo = str(getattr(erro, "code", "") or "")
    status = _numero(getattr(erro, "status", None))
    texto = _texto(erro)
    nomes = _nomes_da_classe(erro)

    if codigo in _CODIGOS_SESSAO or status in _STATUS_SESSAO or "jwt expired" in texto or nomes & _NOMES_SESSAO:
        return Falha(SESSAO_EXPIRADA, MENSAGEM_SESSAO, False)
    if codigo in _CODIGOS_PERMISSAO or status in _STATUS_PERMISSAO:
        return Falha(SEM_PERMISSAO, MENSAGEM_PERMISSAO, False)
    if codigo == "P0001":
        # `raise exception` das RPCs: o texto foi escrito para quem usa o sistema
        mensagem = getattr(erro, "message", None)
        if mensagem:
            return Falha(VALIDACAO, str(mensagem), False)
    if codigo in _MENSAGENS_POR_CODIGO:
        categoria, mensagem = _MENSAGENS_POR_CODIGO[codigo]
        return Falha(categoria, mensagem, False)
    if status in _STATUS_INDISPONIVEL or nomes & _NOMES_REDE or isinstance(erro, (OSError, TimeoutError)):
        return Falha(INDISPONIVEL, MENSAGEM_INDISPONIVEL, True)
    if codigo:
        return Falha(DESCONHECIDO, MENSAGEM_DESCONHECIDO, False)
    # Exceção sem código nem rede reconhecível: o mais provável é o serviço fora do ar
    # ou segredos errados; vale tentar de novo antes de mexer em configuração.
    return Falha(DESCONHECIDO, MENSAGEM_SERVICO, True)


def eh_repeticao_de_envio(erro):
    """True quando o banco recusou a gravação por já ter recebido a mesma `chave_operacao`
    (índice único `uq_*_chave_operacao`): o primeiro envio valeu e este é só uma repetição."""
    return str(getattr(erro, "code", "") or "") == "23505" and "chave_operacao" in _texto(erro)
