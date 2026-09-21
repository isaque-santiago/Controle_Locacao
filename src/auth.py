"""Login, logout e guarda de página (require_login)."""

import streamlit as st


def require_login() -> None:
    """Garante que só o dono autenticado acesse a página."""
    if not st.session_state.get("usuario"):
        st.stop()


def login(email: str, senha: str) -> None:
    raise NotImplementedError


def logout() -> None:
    st.session_state.pop("usuario", None)
