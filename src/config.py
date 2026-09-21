"""Leitura de st.secrets / variáveis de ambiente."""

import streamlit as st


def get_supabase_url() -> str:
    return st.secrets["SUPABASE_URL"]


def get_supabase_anon_key() -> str:
    return st.secrets["SUPABASE_ANON_KEY"]
