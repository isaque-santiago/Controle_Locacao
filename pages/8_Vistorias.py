"""Vistorias de entrega e devolução, com checklist e fotos."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Vistorias")
