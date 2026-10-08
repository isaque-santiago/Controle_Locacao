"""Leitura e validação das credenciais públicas do Supabase.

Em produção os valores vêm de variáveis de ambiente. Em desenvolvimento, na falta delas, lê-se
`.streamlit/secrets.toml` (ignorado pelo git; o arquivo guarda só a URL e a anon key do projeto de dev).
"""

import os
import tomllib
from pathlib import Path

_SEGREDOS_DEV = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


def _segredo_do_arquivo(nome: str) -> str | None:
    """Valor de `nome` no arquivo de segredos de desenvolvimento, ou None se não houver."""
    try:
        with _SEGREDOS_DEV.open("rb") as arquivo:
            valor = tomllib.load(arquivo).get(nome)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return valor if isinstance(valor, str) else None


def _ler(nome: str) -> str | None:
    return os.getenv(nome) or _segredo_do_arquivo(nome)


def get_supabase_url() -> str:
    valor = _ler("SUPABASE_URL")
    if not valor or "SEU-PROJETO" in valor:
        raise RuntimeError("SUPABASE_URL não foi configurada.")
    return valor.rstrip("/")


def get_supabase_anon_key() -> str:
    valor = _ler("SUPABASE_ANON_KEY")
    if not valor or valor == "sua-anon-key":
        raise RuntimeError("SUPABASE_ANON_KEY não foi configurada.")
    return valor
