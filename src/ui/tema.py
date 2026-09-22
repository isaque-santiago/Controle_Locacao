"""Tokens visuais do painel operacional definidos em Arquivos/Design_UI.md."""

import streamlit as st


def aplicar():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');
    html, body, [data-testid="stApp"] {font-family: 'IBM Plex Sans', sans-serif;}
    h1,h2,h3 {font-family: 'Barlow Semi Condensed', sans-serif !important;}
    .rotulo {font-family: 'Barlow Semi Condensed', sans-serif; font-weight: 600; letter-spacing: 0.02em;}
    .mono {font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums;}
    .campo {display:flex; flex-direction:column; gap:2px;}
    [data-testid="stMetricValue"] {font-family: 'IBM Plex Mono', monospace;}
    [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.22); padding:1rem; border-radius:4px;}
    [data-testid="stSidebar"] {background:#1E2227; color:#FAFAF9;}
    [data-testid="stSidebar"] p {color:#FAFAF9;}
    [data-testid="stSidebarNav"] a {
      border-left:3px solid transparent;
      color:#9AA0A6;
      position:relative;
      padding-left:2.3rem !important;
    }
    [data-testid="stSidebarNav"] a::before {
      content:"";
      position:absolute;
      left:1.5rem;
      top:50%;
      transform:translateY(-50%);
      width:8px;
      height:8px;
      border-radius:2px;
      background:#585F66;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
      border-left:3px solid #F2B705;
      background:rgba(242,183,5,0.08);
      color:#FAFAF9;
      font-weight:600;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"]::before {background:#F2B705;}
    button[kind="primary"] {background:#1E2227; border-color:#1E2227; color:#FAFAF9;}
    [data-baseweb="tab-highlight"] {background:#1E2227;}
    .block-container {padding-top:2rem;}

    /* Cartão "Hoje" do Dashboard — como em Main.dc.html */
    .st-key-dashboard_card_hoje {
      background:#FAFAF9;
      border:1px solid rgba(30,34,39,.12);
      border-radius:2px;
      padding:0 0 4px 0;
    }
    .st-key-dashboard_card_hoje [data-testid="stHorizontalBlock"] {
      padding:8px 20px 8px 20px;
      border-bottom:1px solid rgba(30,34,39,.12);
      align-items:center;
    }
    .st-key-dashboard_card_hoje [data-testid="stHorizontalBlock"]:last-of-type {
      border-bottom:none;
    }
    .st-key-dashboard_card_hoje button {
      background:#1E2227 !important;
      border:none !important;
      border-radius:6px !important;
      color:#FAFAF9 !important;
      width:30px;
      height:30px;
      padding:0 !important;
      min-height:30px;
    }

    /* Cartões de tabela com linha interativa (Motos — lista/documentos) */
    .st-key-motos_card_lista, .st-key-motos_card_documentos {
      background:#FAFAF9;
      border:1px solid rgba(30,34,39,.12);
      border-radius:2px;
      padding:0 0 4px 0;
    }
    .st-key-motos_card_lista [data-testid="stHorizontalBlock"],
    .st-key-motos_card_documentos [data-testid="stHorizontalBlock"] {
      padding:8px 20px;
      border-bottom:1px solid rgba(30,34,39,.12);
      align-items:center;
    }
    .st-key-motos_card_lista [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-motos_card_documentos [data-testid="stHorizontalBlock"]:last-of-type {
      border-bottom:none;
    }
    .st-key-motos_card_lista button, .st-key-motos_card_documentos button {
      background:transparent !important;
      border:1px solid rgba(30,34,39,.12) !important;
      border-radius:6px !important;
      color:#585F66 !important;
      min-height:1.8rem;
      padding:2px 8px !important;
    }

    /* Pílulas de filtro (Motos — lista) */
    .st-key-motos_filtros button {
      border-radius:20px !important;
      font-size:.8rem !important;
      padding:4px 10px !important;
      min-height:1.9rem;
    }
    .st-key-motos_filtros button[kind="secondary"] {
      background:#FAFAF9 !important;
      border:1px solid rgba(30,34,39,.12) !important;
      color:#1E2227 !important;
    }

    /* Rodapé da sidebar (avatar + nome + Sair) — como em Main.dc.html */
    .st-key-dashboard_sidebar_rodape {
      border-top:1px solid rgba(238,240,240,0.12);
      padding-top:14px;
      margin-top:8px;
    }
    .st-key-dashboard_sidebar_rodape button {
      background:transparent !important;
      border:1px solid rgba(238,240,240,0.24) !important;
      color:#9AA0A6 !important;
      font-size:12px !important;
      padding:4px 8px !important;
      min-height:1.8rem;
    }
    @media (max-width:640px) {
      .block-container {padding:1rem;}
      [data-testid="stMetricValue"] {font-size:1.5rem;}
      [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
