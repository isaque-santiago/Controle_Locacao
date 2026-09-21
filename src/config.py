"""Leitura e validação das credenciais públicas do Supabase."""

import os
import streamlit as st


def get_supabase_url() -> str:
    valor = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    if not valor or "SEU-PROJETO" in valor:
        raise RuntimeError("SUPABASE_URL não foi configurada.")
    return valor.rstrip("/")


def get_supabase_anon_key() -> str:
    valor = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
    if not valor or valor == "sua-anon-key":
        raise RuntimeError("SUPABASE_ANON_KEY não foi configurada.")
    return valor
