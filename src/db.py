"""Fábrica do cliente Supabase (com sessão do usuário, para valer o RLS)."""

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar

from supabase import Client, ClientOptions, create_client

from src.config import get_supabase_anon_key, get_supabase_url

# Cliente da requisição web (FastAPI).
_CLIENTE_REQUISICAO: ContextVar[Client | None] = ContextVar(
    "cliente_requisicao", default=None
)

# Id do usuário da requisição web: chave do cache e dos controles por usuário.
_USUARIO_REQUISICAO: ContextVar[str | None] = ContextVar(
    "usuario_requisicao", default=None
)

# Ganchos do frontend antigo (Streamlit), registrados por `src/ui/sessao_streamlit.py`.
# Somem junto com ele; o app web nunca os registra.
_CLIENTE_ALTERNATIVO: Callable[[], Client] | None = None
_USUARIO_ALTERNATIVO: Callable[[], str | None] | None = None


def registrar_origem_alternativa(
    cliente: Callable[[], Client], usuario_id: Callable[[], str | None]
) -> None:
    """Registra de onde vêm o cliente e o usuário quando não há requisição web."""
    global _CLIENTE_ALTERNATIVO, _USUARIO_ALTERNATIVO
    _CLIENTE_ALTERNATIVO = cliente
    _USUARIO_ALTERNATIVO = usuario_id


def criar_cliente_anonimo() -> Client:
    """Cliente novo, sem usuário (anon key), para entrar ou renovar a sessão.

    Sem renovação automática nem persistência: no app web quem guarda e renova os
    tokens é o servidor de sessões."""
    return create_client(
        get_supabase_url(),
        get_supabase_anon_key(),
        ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def criar_cliente_autenticado(access_token: str) -> Client:
    """Cliente com o token do usuário (a RLS vale), sem chamada de rede extra.

    Usa a anon key; a service_role nunca é usada no app."""
    return create_client(
        get_supabase_url(),
        get_supabase_anon_key(),
        ClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def definir_cliente_da_requisicao(cliente: Client | None) -> None:
    """Define o cliente que `get_client()` devolve no contexto atual (requisição web)."""
    _CLIENTE_REQUISICAO.set(cliente)


def definir_usuario_da_requisicao(usuario_id: str | None) -> None:
    """Define o usuário da requisição web (usado por `usuario_id_atual`)."""
    _USUARIO_REQUISICAO.set(usuario_id)


def usuario_id_atual() -> str | None:
    """Id do usuário logado na requisição web. None sem login.

    Quem guarda dados que dependem da RLS (cache, controles) deve usar este id na chave e,
    sem ele, não guardar nada: assim dois usuários nunca compartilham a mesma entrada."""
    da_requisicao = _USUARIO_REQUISICAO.get()
    if da_requisicao:
        return da_requisicao
    if _USUARIO_ALTERNATIVO is not None:
        return _USUARIO_ALTERNATIVO()
    return None


@contextmanager
def usar_cliente(cliente: Client):
    """Usa `cliente` como o `get_client()` do bloco (ex.: consultar o papel no login)."""
    marca = _CLIENTE_REQUISICAO.set(cliente)
    try:
        yield cliente
    finally:
        _CLIENTE_REQUISICAO.reset(marca)


def get_client() -> Client:
    """Retorna o cliente Supabase do contexto atual (a requisição web)."""
    cliente_da_requisicao = _CLIENTE_REQUISICAO.get()
    if cliente_da_requisicao is not None:
        return cliente_da_requisicao
    if _CLIENTE_ALTERNATIVO is not None:
        return _CLIENTE_ALTERNATIVO()
    raise RuntimeError("Não há cliente Supabase no contexto atual.")
