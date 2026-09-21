"""Cadastro de clientes (locatários)."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Clientes")
