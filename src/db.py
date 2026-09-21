"""Fábrica do cliente Supabase (com sessão do usuário)."""

from supabase import Client, create_client

from src.config import get_supabase_anon_key, get_supabase_url


def get_client() -> Client:
    return create_client(get_supabase_url(), get_supabase_anon_key())
