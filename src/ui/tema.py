"""Tokens visuais do painel operacional definidos em Arquivos/Design_UI.md."""

import streamlit as st

from src.db import ler_tema_escuro_cookie


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

    /* Cartões de tabela com linha interativa (Motos/Clientes/Contratos — lista/documentos) */
    .st-key-motos_card_lista, .st-key-motos_card_documentos, .st-key-clientes_card_lista,
    .st-key-contratos_card_lista, .st-key-manutencao_card_historico,
    .st-key-manutencao_card_catalogo, .st-key-vistorias_card_lista, .st-key-documentos_card_lista,
    [class*="st-key-cobrancas_card"] {
      background:#FAFAF9;
      border:1px solid rgba(30,34,39,.12);
      border-radius:2px;
      padding:0 0 4px 0;
    }
    .st-key-motos_card_lista [data-testid="stHorizontalBlock"],
    .st-key-motos_card_documentos [data-testid="stHorizontalBlock"],
    .st-key-clientes_card_lista [data-testid="stHorizontalBlock"],
    .st-key-contratos_card_lista [data-testid="stHorizontalBlock"],
    .st-key-manutencao_card_historico [data-testid="stHorizontalBlock"],
    .st-key-manutencao_card_catalogo [data-testid="stHorizontalBlock"],
    .st-key-vistorias_card_lista [data-testid="stHorizontalBlock"],
    .st-key-documentos_card_lista [data-testid="stHorizontalBlock"],
    [class*="st-key-cobrancas_card"] [data-testid="stHorizontalBlock"] {
      padding:8px 20px;
      border-bottom:1px solid rgba(30,34,39,.12);
      align-items:center;
    }
    .st-key-motos_card_lista [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-motos_card_documentos [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-clientes_card_lista [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-contratos_card_lista [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-manutencao_card_historico [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-manutencao_card_catalogo [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-vistorias_card_lista [data-testid="stHorizontalBlock"]:last-of-type,
    .st-key-documentos_card_lista [data-testid="stHorizontalBlock"]:last-of-type,
    [class*="st-key-cobrancas_card"] [data-testid="stHorizontalBlock"]:last-of-type {
      border-bottom:none;
    }
    .st-key-motos_card_lista button, .st-key-motos_card_documentos button,
    .st-key-clientes_card_lista button, .st-key-contratos_card_lista button,
    .st-key-manutencao_card_historico button,
    .st-key-manutencao_card_catalogo button, .st-key-vistorias_card_lista button,
    .st-key-documentos_card_lista button,
    [class*="st-key-cobrancas_card"] button {
      background:transparent !important;
      border:1px solid rgba(30,34,39,.12) !important;
      border-radius:6px !important;
      color:#585F66 !important;
      min-height:1.8rem;
      padding:2px 8px !important;
    }

    /* Pílulas de filtro (Motos/Clientes/Contratos — lista, e periodicidade do assistente) */
    .st-key-motos_filtros button, .st-key-clientes_filtros button,
    .st-key-contratos_filtros button, .st-key-contrato_periodicidade button,
    [class*="st-key-manutencao_filtros"] button, .st-key-documentos_filtros button, [class*="st-key-vistorias_filtros"] button,
    .st-key-relatorios_filtros button {
      border-radius:20px !important;
      font-size:.8rem !important;
      padding:4px 10px !important;
      min-height:1.9rem;
    }
    .st-key-motos_filtros button[kind="secondary"], .st-key-clientes_filtros button[kind="secondary"],
    .st-key-contratos_filtros button[kind="secondary"], .st-key-contrato_periodicidade button[kind="secondary"],
    [class*="st-key-manutencao_filtros"] button[kind="secondary"], .st-key-documentos_filtros button[kind="secondary"],
    [class*="st-key-vistorias_filtros"] button[kind="secondary"],
    .st-key-relatorios_filtros button[kind="secondary"] {
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
    /* Configurações — cartões de até 780px, como em Configuracoes.dc.html */
    .st-key-config_pagina {max-width:780px; gap:20px;}
    .st-key-config_pagina [data-testid="stForm"] {padding:0; gap:20px;}
    [class*="st-key-config_card"] {
      background:#FAFAF9;
      border:1px solid rgba(30,34,39,.12);
      border-radius:2px;
      padding:22px 26px;
    }
    [class*="st-key-config_card"] label p {font-size:12px; color:#585F66;}
    [class*="st-key-config_card"] input {font-family:'IBM Plex Mono', monospace;}
    @media (max-width:640px) {
      .block-container {padding:1rem;}
      [data-testid="stMetricValue"] {font-size:1.5rem;}
      [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
    if tema_escuro_ativo():
        st.markdown(_CSS_MODO_ESCURO, unsafe_allow_html=True)


# Modo escuro com paleta própria (não é inversão do claro): fundos em camadas
# (página < cartão < campo), texto principal ~14:1 e secundário >= 6:1 sobre o cartão;
# cores de status clareadas para manter contraste >= 4,5:1.
_CSS_MODO_ESCURO = """
<style>
:root {
  --e-fundo:#15181C; --e-cartao:#22272D; --e-campo:#2B3138; --e-realce:#343B43;
  --e-linha:rgba(238,240,240,.14); --e-texto:#ECEEF0; --e-texto2:#B4BBC3; --e-texto3:#9BA3AC;
}
[data-testid="stApp"] {color-scheme:dark;}
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background:var(--e-fundo) !important; color:var(--e-texto) !important;
}
[data-testid="stHeader"] {background:rgba(21,24,28,.9) !important;}
[data-testid="stHeader"] * {color:var(--e-texto2) !important;}
[data-testid="stSidebar"] {background:#1B1F24 !important; border-right:1px solid var(--e-linha);}

/* Texto nativo do Streamlit */
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
[data-testid="stMain"] h4, [data-testid="stMain"] h5, [data-testid="stMain"] h6,
[data-testid="stMain"] p, [data-testid="stMain"] li, [data-testid="stMain"] label,
[data-testid="stMain"] [data-testid="stMarkdownContainer"],
[data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stMain"] [data-testid="stMetricLabel"] p,
[data-testid="stMain"] [data-testid="stMetricValue"],
[data-testid="stMain"] summary, [data-testid="stMain"] summary p {color:var(--e-texto) !important;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
[data-testid="stMain"] small, [data-testid="stMain"] [data-testid="stMetricDelta"] {color:var(--e-texto2) !important;}
[data-testid="stMain"] a {color:#F2B705;}
[data-testid="stMain"] code {background:var(--e-campo); color:var(--e-texto);}
hr {border-color:var(--e-linha) !important;}

/* Cores inline dos módulos (tokens do modo claro -> equivalentes escuros) */
[data-testid="stApp"] [style*="color:#1E2227" i], [data-testid="stApp"] [style*="color: rgb(30, 34, 39)"] {color:var(--e-texto) !important;}
[data-testid="stApp"] [style*="color:#585F66" i], [data-testid="stApp"] [style*="color: rgb(88, 95, 102)"] {color:var(--e-texto2) !important;}
[data-testid="stApp"] [style*="color:#9AA0A6" i], [data-testid="stApp"] [style*="color: rgb(154, 160, 166)"] {color:var(--e-texto3) !important;}
[data-testid="stApp"] [style*="color:#D64545" i], [data-testid="stApp"] [style*="color: rgb(214, 69, 69)"] {color:#FF8080 !important;}
[data-testid="stApp"] [style*="color:#2F9E6E" i], [data-testid="stApp"] [style*="color: rgb(47, 158, 110)"] {color:#4CC994 !important;}
[data-testid="stApp"] [style*="color:#8a6600" i], [data-testid="stApp"] [style*="color: rgb(138, 102, 0)"] {color:#F2B705 !important;}
[data-testid="stApp"] [style*="background:#FAFAF9" i], [data-testid="stApp"] [style*="background: rgb(250, 250, 249)"],
[data-testid="stApp"] [class*="st-key-config_card"],
[data-testid="stApp"] [class*="_card_"], [data-testid="stApp"] [class*="_card"] {
  background:var(--e-cartao) !important;
}
[data-testid="stApp"] [style*="background:#EEF0F0" i], [data-testid="stApp"] [style*="background: rgb(238, 240, 240)"] {background:var(--e-fundo) !important;}
[data-testid="stApp"] [style*="background:#1E2227" i], [data-testid="stApp"] [style*="background: rgb(30, 34, 39)"] {background:var(--e-realce) !important;}
[data-testid="stApp"] [style*="background:rgba(30,34,39"], [data-testid="stApp"] [style*="background: rgba(30, 34, 39"] {background:rgba(238,240,240,.16) !important;}
[data-testid="stApp"] [style*="rgba(30,34,39"], [data-testid="stApp"] [style*="rgba(30, 34, 39"] {border-color:var(--e-linha) !important;}
[data-testid="stApp"] [class*="_card"], [data-testid="stApp"] [class*="_card"] [data-testid="stHorizontalBlock"] {
  border-color:var(--e-linha) !important;
}
[data-testid="stApp"] [style*="background:rgba(242,183,5,0.12)"], [data-testid="stApp"] [style*="background: rgba(242, 183, 5, 0.12)"] {background:rgba(242,183,5,.18) !important;}

/* Cartões, métricas e tabelas */
[data-testid="stMetric"] {background:var(--e-cartao) !important; border-color:var(--e-linha) !important;}
[data-testid="stTable"], [data-testid="stTable"] th,
[data-testid="stTable"] td {background:var(--e-cartao) !important; color:var(--e-texto) !important;}
/* O grid é um canvas com o tema claro: inverte luminosidade preservando o matiz */
[data-testid="stDataFrame"] {filter:invert(1) hue-rotate(180deg); border-radius:4px; overflow:hidden;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--e-linha) !important;}
[data-testid="stExpander"], [data-testid="stExpander"] details {
  background:var(--e-cartao) !important; border-color:var(--e-linha) !important;
}
[data-testid="stForm"] {border-color:var(--e-linha) !important;}

/* Campos */
[data-baseweb="input"], [data-baseweb="input"] > div, [data-baseweb="base-input"],
[data-baseweb="select"] > div, [data-baseweb="textarea"], [data-baseweb="textarea"] > div,
textarea, [data-testid="stNumberInput"] button, [data-testid="stTextInputRootElement"],
[data-testid="stDateInputField"], [data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stTimeInput"] [data-baseweb="select"] > div, [data-testid="stTextAreaRootElement"] {
  background:var(--e-campo) !important; color:var(--e-texto) !important; border-color:var(--e-linha) !important;
}
input, textarea, [data-baseweb="select"] div, [data-baseweb="select"] span {
  color:var(--e-texto) !important; -webkit-text-fill-color:var(--e-texto) !important;
}
input::placeholder, textarea::placeholder {color:var(--e-texto3) !important; -webkit-text-fill-color:var(--e-texto3) !important;}
[data-testid="stSelectbox"] div:has(> input), [data-testid="stMultiSelect"] div:has(> input) {
  background:var(--e-campo) !important; border-color:var(--e-linha) !important;
}
[data-testid="stSelectbox"] button, [data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg {
  color:var(--e-texto2) !important; fill:var(--e-texto2) !important;
}
[role="listbox"], [role="listbox"] [role="option"], [data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] * {
  background:var(--e-campo) !important; color:var(--e-texto) !important;
}
[role="listbox"] [role="option"]:hover, [role="listbox"] [aria-selected="true"] {
  background:var(--e-realce) !important;
}
input:disabled, textarea:disabled {opacity:.6;}
[data-testid="stDateInputField"] input {opacity:1;}
[data-testid="stDateInputField"] span, [data-testid="stDateInputField"] div {
  color:var(--e-texto) !important; -webkit-text-fill-color:var(--e-texto) !important;
}
[data-baseweb="select"] svg, [data-testid="stNumberInput"] svg {fill:var(--e-texto2) !important;}
[data-testid="stFileUploaderDropzone"] {background:var(--e-campo) !important; border-color:var(--e-linha) !important;}
[data-testid="stFileUploaderDropzone"] * {color:var(--e-texto2) !important;}

/* Menus suspensos (renderizados fora do stApp) */
[data-baseweb="popover"] [data-baseweb="menu"], [data-baseweb="popover"] ul,
[data-baseweb="popover"] > div, [data-baseweb="calendar"], [data-baseweb="calendar"] * {
  background:var(--e-campo) !important; color:var(--e-texto) !important;
}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] [aria-selected="true"] {
  background:var(--e-realce) !important;
}

/* Rádio, checkbox, toggle */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label, [data-testid="stToggle"] label,
[data-testid="stRadio"] label p, [data-testid="stCheckbox"] label p {color:var(--e-texto) !important;}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] label p {color:#ECEEF0 !important;}

/* Botões */
button[kind="primary"] {background:#F2B705 !important; border-color:#F2B705 !important; color:#15181C !important;}
button[kind="primary"]:hover {background:#FFC933 !important; border-color:#FFC933 !important;}
button[kind="primary"] * {color:#15181C !important;}
button[kind="secondary"], [data-testid="stDownloadButton"] button {
  background:var(--e-campo); color:var(--e-texto); border-color:var(--e-linha);
}
button[kind="secondary"]:hover {background:var(--e-realce); border-color:var(--e-texto3); color:#FFFFFF;}
button[kind="secondary"] * {color:inherit !important;}
button[kind="tertiary"], button[kind="tertiary"] * {color:var(--e-texto2) !important;}
[data-testid="stApp"] [class*="_card"] button, [data-testid="stApp"] [class*="_card"] button * {
  color:var(--e-texto2) !important; border-color:var(--e-linha) !important;
}
[data-testid="stApp"] [class*="_filtros"] button[kind="secondary"] {
  background:var(--e-cartao) !important; color:var(--e-texto) !important; border-color:var(--e-linha) !important;
}
[data-testid="stApp"] [class*="_filtros"] button[kind="primary"] {
  background:#F2B705 !important; color:#15181C !important;
}
[data-testid="stApp"] .st-key-dashboard_card_hoje button {background:var(--e-realce) !important;}
[data-testid="stSidebar"] button[kind="secondary"] {background:transparent; color:#B4BBC3;}

/* Abas */
[data-baseweb="tab-list"] {border-bottom:1px solid var(--e-linha);}
[data-baseweb="tab"], [data-baseweb="tab"] p {color:var(--e-texto2) !important; background:transparent !important;}
[data-baseweb="tab"][aria-selected="true"], [data-baseweb="tab"][aria-selected="true"] p {color:#F2B705 !important;}
[data-baseweb="tab-highlight"] {background:#F2B705 !important;}
[data-baseweb="tab-border"] {background:var(--e-linha) !important;}
/* Abas do Streamlit atual (react-aria): indicador amarelo e trilho discreto */
.react-aria-TabList {border-bottom:1px solid var(--e-linha) !important; box-shadow:none !important;}
.react-aria-Tab, .react-aria-Tab * {color:var(--e-texto2) !important; background:transparent !important;}
.react-aria-Tab:hover, .react-aria-Tab:hover * {color:var(--e-texto) !important;}
.react-aria-Tab[aria-selected="true"], .react-aria-Tab[aria-selected="true"] * {color:#F2B705 !important;}
div.react-aria-SelectionIndicator {background:#F2B705 !important; border-color:#F2B705 !important;}

/* Alertas nativos */
[data-testid="stAlert"] {background:var(--e-cartao) !important; border:1px solid var(--e-linha);}
[data-testid="stAlert"] * {color:var(--e-texto) !important;}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {border-left:4px solid #FF8080;}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {border-left:4px solid #4CC994;}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {border-left:4px solid #F2B705;}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {border-left:4px solid #6CB4EE;}

/* Diálogos, tooltips e gráficos */
[data-testid="stDialog"] > div, [role="dialog"] {background:var(--e-cartao) !important; color:var(--e-texto) !important;}
[data-testid="stTooltipContent"], [data-baseweb="tooltip"] > div {background:var(--e-realce) !important; color:var(--e-texto) !important;}
[data-testid="stPlotlyChart"] .main-svg {background:transparent !important;}
[data-testid="stPlotlyChart"] text {fill:var(--e-texto2) !important;}
[data-testid="stPlotlyChart"] .gridlayer path, [data-testid="stPlotlyChart"] .zerolinelayer path {stroke:var(--e-linha) !important;}
</style>
"""
