"""Matriz de viewports, perfis de navegador e inventário de páginas da suíte e2e."""

import os
from dataclasses import dataclass

# Larguras e alturas de referência do Plano_Melhorias_UI_UX.md (Etapa 9).
VIEWPORTS = {
    320: 568,
    390: 844,
    768: 1024,
    1024: 768,
    1440: 900,
}

TEMAS = ("claro", "escuro")

# Alvo mínimo de toque adotado pelo projeto (px CSS).
ALVO_MINIMO = 44

# Largura até a qual o perfil "chromium-movel" (toque, viewport móvel) faz sentido.
LARGURA_MAXIMA_MOVEL = 768


@dataclass(frozen=True)
class Perfil:
    nome: str
    navegador: str  # chromium | firefox | webkit
    movel: bool = False


PERFIS = {
    "chromium-desktop": Perfil("chromium-desktop", "chromium"),
    "chromium-movel": Perfil("chromium-movel", "chromium", movel=True),
    "firefox": Perfil("firefox", "firefox"),
    "webkit": Perfil("webkit", "webkit"),
}
PERFIL_PADRAO = "chromium-desktop"


@dataclass(frozen=True)
class Pagina:
    titulo: str  # texto do menu lateral (st.Page title)
    caminho: str  # url_path do Streamlit ("" = página inicial)


# Espelha app.py. Se as páginas mudarem lá, ajuste aqui.
PAGINAS = (
    Pagina("Dashboard", ""),
    Pagina("Motos", "Motos"),
    Pagina("Clientes", "Clientes"),
    Pagina("Contratos", "Contratos"),
    Pagina("Cobranças", "Cobrancas"),
    Pagina("Manutenção", "Manutencao"),
    Pagina("Documentos", "Documentos"),
    Pagina("Vistorias", "Vistorias"),
    Pagina("Relatórios", "Relatorios"),
    Pagina("Configurações", "Configuracoes"),
)

# Estados de dados possíveis (ver e2e/README.md e supabase/seed_e2e.sql).
ESTADOS_DADOS = ("vazio", "normal", "extremo")


def base_url() -> str:
    return os.environ.get("E2E_BASE_URL", "http://localhost:8501").rstrip("/")


def credenciais() -> tuple[str, str] | None:
    """Usuário de teste do projeto Supabase de DESENVOLVIMENTO, lido do ambiente.

    Nunca vem de arquivo versionado e nunca é impresso."""
    email = os.environ.get("E2E_EMAIL", "").strip()
    senha = os.environ.get("E2E_SENHA", "")
    return (email, senha) if email and senha else None


def estado_dados() -> str:
    return os.environ.get("E2E_DADOS", "normal")
