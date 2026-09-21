"""Alertas, registro e catálogo de manutenção."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Manutenção")
