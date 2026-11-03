from pathlib import Path
from unittest.mock import patch

import pytest

from src import config


def test_configuracao_aceita_variaveis_de_ambiente(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://projeto.supabase.co/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "chave-publica")
    assert config.get_supabase_url() == "https://projeto.supabase.co"
    assert config.get_supabase_anon_key() == "chave-publica"


def test_configuracao_ausente_exibe_causa(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    with patch("src.config._SEGREDOS_DEV", Path("/inexistente/.env")):
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            config.get_supabase_url()
        with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
            config.get_supabase_anon_key()


def test_locador_vem_das_variaveis_de_ambiente_e_ignora_vazias(monkeypatch):
    from src import config

    monkeypatch.setattr(config, "_SEGREDOS_DEV", config.Path("/inexistente/.env"))
    for campo in config.CAMPOS_LOCADOR:
        monkeypatch.delenv(f"LOCADOR_{campo.upper()}", raising=False)
    assert config.get_locador() == {}
    monkeypatch.setenv("LOCADOR_NOME", " Empresa Exemplo ")
    monkeypatch.setenv("LOCADOR_CNPJ", "")
    assert config.get_locador() == {"nome": "Empresa Exemplo"}
