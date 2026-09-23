"""Fábrica do cliente Supabase (com sessão do usuário, para valer o RLS)."""

import streamlit as st
from streamlit_cookies_controller import CookieController
from supabase import Client, create_client

from src.config import get_supabase_anon_key, get_supabase_url

_CHAVE_CLIENTE = "supabase_client"
_CHAVE_COOKIES = "cookie_controller"
_COOKIE_REFRESH_TOKEN = "sb_refresh_token"
_COOKIE_ULTIMA_ATIVIDADE = "sb_ultima_atividade"
_COOKIE_TEMA_ESCURO = "tema_escuro"
_VALIDADE_TEMA_SEGUNDOS = 60 * 60 * 24 * 365
_LIMITE_INATIVIDADE_SEGUNDOS = 1800
_VALIDADE_LEMBRAR_SEGUNDOS = 60 * 60 * 24 * 7


def _conexao_https() -> bool:
    """True quando a requisição chegou por HTTPS (direto ou atrás de proxy).

    O Streamlit Cloud atende atrás de um proxy que informa o protocolo em
    x-forwarded-proto; em localhost (HTTP) devolve False.
    """
    try:
        contexto = st.context
        protocolo = str(contexto.headers.get("x-forwarded-proto") or "")
        if protocolo.split(",")[0].strip().lower() == "https":
            return True
        return str(contexto.url or "").lower().startswith("https://")
    except Exception:
        return False


def _opcoes_cookie() -> dict:
    """Atributos dos cookies de sessão: SameSite=lax e Secure quando em HTTPS."""
    opcoes = {"same_site": "lax"}
    if _conexao_https():
        opcoes["secure"] = True
    return opcoes


def get_client() -> Client:
    """Retorna o cliente Supabase da sessão atual, criando se necessário."""
    if _CHAVE_CLIENTE not in st.session_state:
        st.session_state[_CHAVE_CLIENTE] = create_client(
            get_supabase_url(), get_supabase_anon_key()
        )
    return st.session_state[_CHAVE_CLIENTE]


def _get_cookie_controller() -> CookieController:
    """Retorna o controlador de cookies do navegador (persiste entre refreshes)."""
    if _CHAVE_COOKIES not in st.session_state:
        st.session_state[_CHAVE_COOKIES] = CookieController()
    return st.session_state[_CHAVE_COOKIES]


def set_session_tokens(access_token: str, refresh_token: str) -> None:
    """Aplica os tokens do usuário logado ao cliente, para o RLS valer."""
    get_client().auth.set_session(access_token, refresh_token)
    _get_cookie_controller().set(
        _COOKIE_REFRESH_TOKEN,
        refresh_token,
        max_age=_VALIDADE_LEMBRAR_SEGUNDOS,
        **_opcoes_cookie(),
    )


def clear_session_tokens() -> None:
    """Descarta o cliente autenticado e os cookies de sessão do navegador."""
    st.session_state.pop(_CHAVE_CLIENTE, None)
    controlador = _get_cookie_controller()
    for nome in (_COOKIE_REFRESH_TOKEN, _COOKIE_ULTIMA_ATIVIDADE):
        try:
            controlador.remove(nome)
        except KeyError:
            # A remoção já foi enviada ao navegador; só faltava o item no cache
            # interno do componente (comum logo após um F5).
            pass


def _ler_cookie_da_requisicao(nome: str) -> tuple[bool, str | None]:
    """Lê um cookie enviado no handshake, sem depender do componente assíncrono."""
    try:
        cookies = st.context.cookies
    except AttributeError:
        return False, None

    try:
        valor = cookies[nome]
    except KeyError:
        return True, None
    return True, valor if isinstance(valor, str) else None


def get_refresh_token_cookie() -> str | None:
    """Lê o refresh token guardado no cookie do navegador, se existir."""
    contexto_disponivel, valor = _ler_cookie_da_requisicao(_COOKIE_REFRESH_TOKEN)
    if contexto_disponivel:
        return valor
    return _get_cookie_controller().get(_COOKIE_REFRESH_TOKEN)


def marcar_atividade_cookie() -> None:
    """Renova o cookie de atividade (expira sozinho após inatividade)."""
    _get_cookie_controller().set(
        _COOKIE_ULTIMA_ATIVIDADE,
        "1",
        max_age=_LIMITE_INATIVIDADE_SEGUNDOS,
        **_opcoes_cookie(),
    )


def ler_tema_escuro_cookie() -> bool:
    """True se o navegador guardou a preferência de modo escuro."""
    _, valor = _ler_cookie_da_requisicao(_COOKIE_TEMA_ESCURO)
    return valor == "1"


def salvar_tema_escuro_cookie(escuro: bool) -> None:
    """Guarda a preferência de modo escuro no navegador, para sobreviver ao F5."""
    _get_cookie_controller().set(
        _COOKIE_TEMA_ESCURO,
        "1" if escuro else "0",
        max_age=_VALIDADE_TEMA_SEGUNDOS,
        **_opcoes_cookie(),
    )


def sessao_ativa_no_cookie() -> bool:
    """True se o cookie de atividade ainda não expirou (sem inatividade > limite)."""
    contexto_disponivel, valor = _ler_cookie_da_requisicao(
        _COOKIE_ULTIMA_ATIVIDADE
    )
    if contexto_disponivel:
        return valor is not None
    return _get_cookie_controller().get(_COOKIE_ULTIMA_ATIVIDADE) is not None
