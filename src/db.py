"""Fábrica do cliente Supabase (com sessão do usuário, para valer o RLS)."""

import streamlit as st
from supabase import Client, create_client

from src.config import get_supabase_anon_key, get_supabase_url

_CHAVE_CLIENTE = "supabase_client"


def get_client() -> Client:
    """Retorna o cliente Supabase da sessão atual, criando se necessário."""
    if _CHAVE_CLIENTE not in st.session_state:
        st.session_state[_CHAVE_CLIENTE] = create_client(
            get_supabase_url(), get_supabase_anon_key()
        )
    return st.session_state[_CHAVE_CLIENTE]


def set_session_tokens(access_token: str, refresh_token: str) -> None:
    """Aplica os tokens do usuário logado ao cliente, para o RLS valer."""
    get_client().auth.set_session(access_token, refresh_token)


def clear_session_tokens() -> None:
    """Descarta o cliente autenticado (volta a criar um novo, anônimo)."""
    st.session_state.pop(_CHAVE_CLIENTE, None)
