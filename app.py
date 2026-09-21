"""Ponto de entrada do sistema: login + Dashboard."""

import streamlit as st

from src.ui.dashboard import exibir

st.set_page_config(page_title="Controle de Locação", layout="wide")

exibir()
