"""Leitura e validação das credenciais públicas do Supabase.

Em produção os valores vêm de variáveis de ambiente. Em desenvolvimento, na falta delas, lê-se
`.env` na raiz do projeto (ignorado pelo git; guarda só a URL e a anon key do projeto de dev).
"""

import os
from pathlib import Path

_SEGREDOS_DEV = Path(__file__).resolve().parent.parent / ".env"


def _segredo_do_arquivo(nome: str) -> str | None:
    """Valor de `nome` no `.env` de desenvolvimento (`CHAVE=valor`), ou None se não houver."""
    try:
        linhas = _SEGREDOS_DEV.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        linha = linha.removeprefix("export ").lstrip()
        chave, separador, valor = linha.partition("=")
        if not separador or chave.strip() != nome:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            return valor[1:-1]
        return valor.split(" #", 1)[0].strip()
    return None


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
