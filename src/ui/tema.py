"""Tokens visuais do painel operacional definidos em Arquivos/Design_UI.md."""

import streamlit as st


def aplicar():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');
    html, body, [data-testid="stApp"] {font-family: 'IBM Plex Sans', sans-serif;}
    h1,h2,h3 {font-family: 'Barlow Semi Condensed', sans-serif !important;}
    [data-testid="stMetricValue"] {font-family: 'IBM Plex Mono', monospace;}
    [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.22); padding:1rem; border-radius:4px;}
    [data-testid="stSidebar"] {background:#1E2227; color:#FAFAF9;}
    [data-testid="stSidebar"] a, [data-testid="stSidebar"] p {color:#FAFAF9;}
    [data-testid="stSidebarNav"] a[aria-current="page"] {border-left:3px solid #F2B705; background:#2B3036;}
    button[kind="primary"] {background:#1E2227; border-color:#1E2227; color:#FAFAF9;}
    [data-baseweb="tab-highlight"] {background:#585F66;}
    .block-container {padding-top:2rem;}
    @media (max-width:640px) {
      .block-container {padding:1rem;}
      [data-testid="stMetricValue"] {font-size:1.5rem;}
      [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
