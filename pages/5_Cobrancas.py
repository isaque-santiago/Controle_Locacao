"""Cobranças: hoje, atrasadas, próximas e pagas; registro de pagamento."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Cobranças")
