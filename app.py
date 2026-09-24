"""Ponto de entrada do sistema: navegação com Dashboard como página inicial."""

import streamlit as st

from src.auth import require_login
from src.ui.tema import aplicar

st.set_page_config(page_title="Controle de Locação", layout="wide")

paginas = [
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

pagina = st.navigation(paginas)

# Tema, login e barra lateral são montados aqui, uma única vez por execução e sempre
# na mesma posição da tela, em vez de refeitos por cada página (o que fazia a
# barra lateral e o estilo piscarem a cada troca de página).
aplicar()
require_login()
st.session_state["shell_pronto"] = True

pagina.run()
