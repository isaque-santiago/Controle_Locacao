"""O núcleo e o app web não podem depender do Streamlit (ele será removido na Fase 4)."""

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PASTAS_SEM_STREAMLIT = ("domain", "repositories", "services", "web")
ARQUIVOS_SEM_STREAMLIT = ("config.py", "db.py")


def _arquivos():
    for pasta in PASTAS_SEM_STREAMLIT:
        yield from (RAIZ / "src" / pasta).rglob("*.py")
    for nome in ARQUIVOS_SEM_STREAMLIT:
        yield RAIZ / "src" / nome


@pytest.mark.parametrize("arquivo", sorted(_arquivos()), ids=lambda a: str(a.relative_to(RAIZ)))
def test_codigo_do_nucleo_nao_menciona_streamlit_nem_src_ui_com_streamlit(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    assert "import streamlit" not in texto and "from streamlit" not in texto
    assert "import sessao_streamlit" not in texto and "ui.sessao_streamlit import" not in texto


def test_app_web_sobe_sem_carregar_o_streamlit():
    codigo = (
        f"import sys; sys.path.insert(0, {str(RAIZ)!r}); import src.web.app, src.db, src.config; "
        "sys.exit(1 if any(m == 'streamlit' or m.startswith('streamlit.') for m in sys.modules) else 0)"
    )
    resultado = subprocess.run([sys.executable, "-I", "-c", codigo], cwd=RAIZ, capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr


def test_get_client_sem_requisicao_nem_frontend_antigo_avisa(monkeypatch):
    from src import db

    monkeypatch.setattr(db, "_CLIENTE_ALTERNATIVO", None)
    monkeypatch.setattr(db, "_USUARIO_ALTERNATIVO", None)
    with pytest.raises(RuntimeError, match="cliente Supabase"):
        db.get_client()
    assert db.usuario_id_atual() is None


def test_config_le_o_arquivo_de_segredos_de_dev_quando_nao_ha_variavel(monkeypatch, tmp_path):
    from src import config

    arquivo = tmp_path / "secrets.toml"
    arquivo.write_text('SUPABASE_URL = "https://dev.supabase.co/"\nSUPABASE_ANON_KEY = "chave-dev"\n', encoding="utf-8")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setattr(config, "_SEGREDOS_DEV", arquivo)
    assert config.get_supabase_url() == "https://dev.supabase.co"
    assert config.get_supabase_anon_key() == "chave-dev"


def test_variavel_de_ambiente_tem_prioridade_sobre_o_arquivo(monkeypatch, tmp_path):
    from src import config

    arquivo = tmp_path / "secrets.toml"
    arquivo.write_text('SUPABASE_URL = "https://arquivo.supabase.co"\n', encoding="utf-8")
    monkeypatch.setenv("SUPABASE_URL", "https://ambiente.supabase.co")
    monkeypatch.setattr(config, "_SEGREDOS_DEV", arquivo)
    assert config.get_supabase_url() == "https://ambiente.supabase.co"
