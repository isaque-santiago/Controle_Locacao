"""Ajustes de acessibilidade na marcação do Streamlit (src/ui/acessibilidade.py) e regras de CSS ligadas a eles."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.ui import acessibilidade

RAIZ = Path(__file__).resolve().parents[1]
CSS = (RAIZ / "src" / "ui" / "estilos.css").read_text(encoding="utf-8")


def test_tema_aplicar_renderiza_sem_erro_e_com_um_unico_bloco_de_script():
    def roteiro():
        from src.ui import tema

        tema.aplicar()

    app = AppTest.from_function(roteiro, default_timeout=20).run()
    assert not app.exception


def test_script_cobre_os_ajustes():
    s = acessibilidade.SCRIPT_A11Y
    # aria-expanded inválido na barra lateral e no campo de data
    assert "removeAttribute('aria-expanded')" in s and "stDateInputField" in s
    # barra recolhida sai da ordem de tabulação
    assert "barra.inert" in s and "data-expandida" in s
    # lista de navegação com semântica válida
    assert "stSidebarNavItems" in s and "'presentation'" in s and "'list'" in s
    # iframe invisível do componente de cookies fora da tabulação
    assert "streamlit_cookies_controller" in s and "'tabindex'" in s
    # marcos de página
    assert "'main'" in s and "'complementary'" in s


def test_script_e_idempotente_e_so_instala_uma_vez():
    s = acessibilidade.SCRIPT_A11Y
    assert "window.__locacaoA11y" in s
    assert "requestAnimationFrame" in s  # agrupa as mutações: não roda a cada nó novo


def test_tema_instala_os_ajustes():
    fonte = (RAIZ / "src" / "ui" / "tema.py").read_text(encoding="utf-8")
    assert "SCRIPT_A11Y" in fonte and fonte.count("st.html(") == 1


def test_regiao_principal_tem_foco_visivel():
    assert '[data-testid="stMain"]:focus-visible' in CSS


def test_legenda_nao_usa_opacidade_reduzida():
    """O Streamlit aplica 60% de opacidade à legenda; com --texto-2 isso cai para ~2,5:1."""
    assert '[data-testid="stCaptionContainer"] {opacity: 1;}' in CSS


def test_titulos_dos_cartoes_de_configuracoes_seguem_o_h1():
    """h1 → h2 (sem pular nível): ordem de títulos exigida pela auditoria de acessibilidade."""
    fonte = (RAIZ / "src" / "ui" / "configuracoes.py").read_text(encoding="utf-8")
    assert '<h2 class="rotulo config-titulo">' in fonte and "<h3" not in fonte
