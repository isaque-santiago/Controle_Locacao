"""Ponto de entrada do sistema: navegação por papel (dono ou locatário)."""

from pathlib import Path

import streamlit as st

from src.auth import require_login
from src.domain.troca_oleo import PAPEL_DONO, PAPEL_LOCATARIO
from src.services import portal_locatario
from src.ui.tema import aplicar

ICONE = Path(__file__).parent / "src" / "ui" / "assets" / "icone.png"

st.set_page_config(page_title="Controle de Locação", page_icon=str(ICONE), layout="wide")

# Menu do dono agrupado por área de trabalho (as rotas não mudam, só a ordem e os títulos de seção).
GRUPOS_DONO = {
    "Operação": [
        st.Page("pages/1_Dashboard.py", title="Dashboard", default=True),
        st.Page("pages/4_Contratos.py", title="Contratos"),
        st.Page("pages/5_Cobrancas.py", title="Cobranças"),
    ],
    "Cadastros": [
        st.Page("pages/2_Motos.py", title="Motos"),
        st.Page("pages/3_Clientes.py", title="Clientes"),
    ],
    "Frota": [
        st.Page("pages/6_Manutencao.py", title="Manutenção"),
        st.Page("pages/7_Documentos.py", title="Documentos"),
        st.Page("pages/8_Vistorias.py", title="Vistorias"),
    ],
    "Gestão": [st.Page("pages/9_Relatorios.py", title="Relatórios")],
    "Sistema": [st.Page("pages/10_Configuracoes.py", title="Configurações")],
}
PAGINAS_DONO = [pagina for grupo in GRUPOS_DONO.values() for pagina in grupo]
ARQUIVO_PORTAL = "pages/11_Portal_Locatario.py"

# Antes do login o menu fica oculto (assim o Streamlit também não lista as páginas da
# pasta pages/) e todas as páginas estão registradas, para qualquer endereço abrir o
# login e não uma tela de "página não encontrada". Depois do login, com o papel
# conhecido, o menu real é montado: cada papel só vê as suas telas. O menu apenas
# evita mostrar telas que o usuário não pode usar; quem protege os dados é a RLS/RPC.
st.navigation([*PAGINAS_DONO, st.Page(ARQUIVO_PORTAL, title="Troca de óleo")], position="hidden")

# Tema, login e barra lateral são montados aqui, uma única vez por execução e sempre
# na mesma posição da tela, em vez de refeitos por cada página (o que fazia a
# barra lateral e o estilo piscarem a cada troca de página).
aplicar()
require_login()

papel = portal_locatario.papel_atual()
if papel not in (PAPEL_DONO, PAPEL_LOCATARIO):
    st.error(
        "Este usuário não tem acesso ao sistema. Peça ao proprietário para criar o seu "
        "acesso ao portal."
    )
    st.stop()

pagina = st.navigation(
    [st.Page(ARQUIVO_PORTAL, title="Troca de óleo", default=True)]
    if papel == PAPEL_LOCATARIO
    else GRUPOS_DONO,
    expanded=True,
)
st.session_state["shell_pronto"] = True

pagina.run()
