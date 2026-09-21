"""Configurações: multa, juros, carência, limites de alerta, backup manual."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Configurações")
