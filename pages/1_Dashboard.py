"""Dashboard: KPIs, ocupação, cobranças e alertas."""

import streamlit as st

from src.auth import require_login

require_login()

st.title("Dashboard")
