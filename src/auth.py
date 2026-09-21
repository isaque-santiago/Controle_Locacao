"""Login, logout e guarda de página (require_login)."""

import streamlit as st

from src.db import clear_session_tokens, get_client, set_session_tokens

_CHAVE_USUARIO = "usuario"


def esta_autenticado() -> bool:
    return _CHAVE_USUARIO in st.session_state


def login(email: str, senha: str) -> None:
    """Autentica no Supabase e guarda o usuário e os tokens na sessão."""
    resposta = get_client().auth.sign_in_with_password(
        {"email": email, "password": senha}
    )
    set_session_tokens(
        resposta.session.access_token, resposta.session.refresh_token
    )
    st.session_state[_CHAVE_USUARIO] = {
        "id": resposta.user.id,
        "email": resposta.user.email,
    }


def logout() -> None:
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    clear_session_tokens()
    st.session_state.pop(_CHAVE_USUARIO, None)


def _exibir_formulario_login() -> None:
    st.title("Entrar")
    with st.form("form_login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        enviado = st.form_submit_button("Entrar")

    if enviado:
        try:
            login(email, senha)
            st.rerun()
        except Exception:
            st.error("E-mail ou senha inválidos.")


def require_login() -> None:
    """Bloqueia a página até o dono estar autenticado; exibe login se não estiver."""
    if not esta_autenticado():
        _exibir_formulario_login()
        st.stop()

    with st.sidebar:
        st.caption(st.session_state[_CHAVE_USUARIO]["email"])
        if st.button("Sair"):
            logout()
            st.rerun()
