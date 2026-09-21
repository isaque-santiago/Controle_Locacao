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
    with patch("src.config.st.secrets", {}):
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            config.get_supabase_url()
        with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
            config.get_supabase_anon_key()
