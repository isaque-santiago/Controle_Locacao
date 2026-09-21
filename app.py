"""Ponto de entrada do sistema: login + Dashboard."""

import streamlit as st

from src.auth import require_login

st.set_page_config(page_title="Controle de Locação", layout="wide")

require_login()

st.title("Controle de Locação de Motos")
