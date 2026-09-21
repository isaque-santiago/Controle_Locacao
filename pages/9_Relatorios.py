"""Relatórios: resultado por moto, custos, inadimplência, fluxo de caixa."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Relatórios")
