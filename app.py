"""Ponto de entrada do sistema: navegação por papel (dono ou locatário)."""

from pathlib import Path

import streamlit as st

from src.auth import require_login
from src.domain.troca_oleo import PAPEL_DONO, PAPEL_LOCATARIO
from src.services import portal_locatario
from src.ui.tema import aplicar

ICONE = Path(__file__).parent / "src" / "ui" / "assets" / "icone.png"

st.set_page_config(page_title="Controle de Locação", page_icon=str(ICONE), layout="wide")

PAGINAS_DONO = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", default=True),
    st.Page("pages/2_Motos.py", title="Motos"),
    st.Page("pages/3_Clientes.py", title="Clientes"),
    st.Page("pages/4_Contratos.py", title="Contratos"),
    st.Page("pages/5_Cobrancas.py", title="Cobranças"),
    st.Page("pages/6_Manutencao.py", title="Manutenção"),
    st.Page("pages/7_Documentos.py", title="Documentos"),
    st.Page("pages/8_Vistorias.py", title="Vistorias"),
    st.Page("pages/9_Relatorios.py", title="Relatórios"),
    st.Page("pages/10_Configuracoes.py", title="Configurações"),
]
PAGINAS_LOCATARIO = [
    st.Page("pages/11_Portal_Locatario.py", title="Troca de óleo", default=True),
]

# O menu depende do papel, que só se conhece depois do login: na primeira execução
# de uma sessão o papel ainda é desconhecido e o menu do dono é o padrão. O papel
# não dá acesso a nada por si só (quem protege os dados é a RLS/RPC no banco); o
# menu apenas evita mostrar ao locatário telas que ele não pode usar.
papel_conhecido = st.session_state.get("papel_usuario")
pagina = st.navigation(PAGINAS_LOCATARIO if papel_conhecido == PAPEL_LOCATARIO else PAGINAS_DONO)

# Tema, login e barra lateral são montados aqui, uma única vez por execução e sempre
# na mesma posição da tela, em vez de refeitos por cada página (o que fazia a
# barra lateral e o estilo piscarem a cada troca de página).
aplicar()
require_login()

papel = portal_locatario.papel_atual()
if papel not in (PAPEL_DONO, PAPEL_LOCATARIO):
    st.error(
        "Este usuário não tem acesso ao sistema. Peça ao proprietário para vincular "
        "o seu e-mail a um cadastro de cliente."
    )
    st.stop()

st.session_state["shell_pronto"] = True

if papel == PAPEL_LOCATARIO and papel_conhecido != PAPEL_LOCATARIO:
    # Primeira execução do locatário na sessão: o menu acima ainda era o do dono.
    # Mostra a tela dele direto (sem st.rerun, que descartaria o cookie de login
    # recém-gravado); a partir da próxima interação o menu já é o do locatário.
    from src.ui.portal_locatario import exibir

    exibir()
    st.stop()

pagina.run()
