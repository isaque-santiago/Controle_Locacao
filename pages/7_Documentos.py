"""Documentos da moto: IPVA, licenciamento, seguro."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Documentos")
