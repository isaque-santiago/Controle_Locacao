"""Tema do painel: carrega o design system (tokens + componentes) e o modo escuro.

Os valores visuais (cores, espaçamento, raio, tipografia) ficam como variáveis CSS em
estilos.css; o modo escuro (estilos_escuro.css) só redefine essas variáveis e ajusta
os widgets nativos do Streamlit. Não coloque regras visuais novas aqui.
"""

from pathlib import Path

import streamlit as st

from src.db import ler_tema_escuro_cookie

_PASTA = Path(__file__).parent
_CACHE_CSS: dict[str, tuple[float, str]] = {}


def _ler_css(nome: str) -> str:
    """Lê o CSS e só o relê quando o arquivo muda (edição vale sem reiniciar o servidor)."""
    caminho = _PASTA / nome
    modificado = caminho.stat().st_mtime
    em_cache = _CACHE_CSS.get(nome)
    if em_cache is None or em_cache[0] != modificado:
        em_cache = (modificado, caminho.read_text(encoding="utf-8"))
        _CACHE_CSS[nome] = em_cache
    return em_cache[1]


_FONTES = (
    "@import url('https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600;700"
    "&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');"
)


def tema_escuro_ativo() -> bool:
    """Modo escuro efetivo: escolha manual, ou o tema do sistema quando automático."""
    preferencia = st.session_state.get("tema_escuro")
    if preferencia is not None:
        return bool(preferencia)
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def aplicar():
    # Após um F5 a sessão é nova: retoma a preferência guardada no cookie
    # (None = automático, acompanha o tema do sistema).
    if "tema_escuro" not in st.session_state:
        st.session_state["tema_escuro"] = ler_tema_escuro_cookie()
    st.markdown(f"<style>{_FONTES}\n{_ler_css('estilos.css')}</style>", unsafe_allow_html=True)
    if tema_escuro_ativo():
        st.markdown(f"<style>{_ler_css('estilos_escuro.css')}</style>", unsafe_allow_html=True)
