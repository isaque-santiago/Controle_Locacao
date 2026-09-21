"""Criação, ficha e encerramento de contratos."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Contratos")
