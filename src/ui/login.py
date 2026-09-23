"""Tela de acesso do proprietário."""

import streamlit as st

from src.ui.tema import tema_escuro_ativo

# Sobrepõe as cores fixas do tema claro da tela de login (fundo, cartão e textos).
_CSS_LOGIN_ESCURO = """
<style>
[data-testid="stAppViewContainer"] > .main, [data-testid="stMain"] {
    background:
        linear-gradient(rgba(238,240,240,.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(238,240,240,.03) 1px, transparent 1px),
        #15181C !important;
    background-size: 32px 32px !important;
}
.login-simbolo {border-color: #ECEEF0 !important; color: #ECEEF0 !important;}
.login-marca strong {color: #ECEEF0 !important;}
.login-marca span, .login-contexto p, .login-acesso {color: #B4BBC3 !important;}
.login-contexto h2 {color: #ECEEF0 !important;}
.login-rodape {color: #9BA3AC !important;}
div[data-testid="stForm"] {
    background: #22272D !important;
    border-color: rgba(238,240,240,.14) !important;
}
div[data-testid="stForm"] label, div[data-testid="stForm"] label p,
div[data-testid="stForm"] [data-testid="stWidgetLabel"] p {color: #ECEEF0 !important;}
div[data-testid="stForm"] button[kind="secondaryFormSubmit"],
div[data-testid="stFormSubmitButton"] button {
    background: #F2B705 !important;
    border-color: #F2B705 !important;
    color: #15181C !important;
}
div[data-testid="stFormSubmitButton"] button * {color: #15181C !important;}
</style>
"""


def exibir() -> tuple[bool, str, str]:
    """Renderiza a tela de login e devolve envio, e-mail e senha."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] {
            display: none;
        }
        [data-testid="stAppViewContainer"] > .main {
            background:
                linear-gradient(rgba(30,34,39,.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(30,34,39,.025) 1px, transparent 1px),
                #EEF0F0;
            background-size: 32px 32px;
        }
        .block-container {
            max-width: 1120px;
            padding-top: 8vh;
            padding-bottom: 3rem;
        }
        .login-marca {
            display: flex;
            align-items: center;
            gap: .75rem;
            margin-bottom: 2.8rem;
        }
        .login-simbolo {
            width: 2.5rem;
            height: 2.5rem;
            box-sizing: border-box;
            display: grid;
            place-items: center;
            border: 2px solid #1E2227;
            border-radius: 50%;
            color: #1E2227;
            font: 600 .72rem 'IBM Plex Mono', monospace;
            letter-spacing: -.04em;
        }
        .login-marca strong {
            display: block;
            font-family: 'Barlow Semi Condensed', sans-serif;
            font-size: 1.2rem;
            line-height: 1;
        }
        .login-marca span {
            color: #585F66;
            font-size: .76rem;
        }
        .login-contexto {
            padding: 2rem 0;
            max-width: 30rem;
        }
        .login-contexto h2 {
            margin: 0 0 .75rem;
            font-size: clamp(2.35rem, 4vw, 3.8rem);
            line-height: 1.05;
        }
        .login-contexto p {
            color: #585F66;
            font-size: 1rem;
            line-height: 1.55;
        }
        .login-trilho {
            width: 5rem;
            height: .3rem;
            margin-top: 1.6rem;
            background: #F2B705;
        }
        .login-acesso {
            margin-bottom: 1rem;
            color: #585F66;
            font-size: .84rem;
        }
        div[data-testid="stForm"] {
            background: #FAFAF9;
            border: 1px solid rgba(30,34,39,.12);
            border-radius: 6px;
            padding: 2rem;
        }
        div[data-testid="stTextInput"] input {
            border-radius: 6px;
        }
        div[data-testid="stFormSubmitButton"] button {
            min-height: 2.75rem;
        }
        .login-rodape {
            margin-top: 1rem;
            color: #9AA0A6;
            font-size: .72rem;
            text-align: center;
        }
        @media (max-width: 768px) {
            .block-container { padding-top: 2rem; }
            .login-contexto { padding: 0 0 1rem; }
            .login-contexto h2 { font-size: 1.8rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if tema_escuro_ativo():
        st.markdown(_CSS_LOGIN_ESCURO, unsafe_allow_html=True)

    st.markdown(
        """
        <div class="login-marca">
            <div class="login-simbolo">CL</div>
            <div><strong>Controle de Locação</strong><span>frota de motos</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    apresentacao, acesso = st.columns([1.15, 1], gap="large")
    with apresentacao:
        st.markdown(
            """
            <div class="login-contexto">
                <div class="painel-sobretitulo">Gestão de frota simplificada</div>
                <h2>Sua operação,<br>sob controle.</h2>
                <p>Acompanhe locações, cobranças, manutenção e documentos da frota em um único painel.</p>
                <div class="login-trilho"></div>
                <div class="login-recursos"><span>01 &nbsp; Locações e clientes</span><span>02 &nbsp; Receitas e cobranças</span><span>03 &nbsp; Manutenção e vistorias</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with acesso:
        st.title("Entrar")
        st.markdown('<div class="login-acesso">Acesso restrito ao proprietário</div>', unsafe_allow_html=True)
        with st.form("form_login"):
            email = st.text_input(
                "E-mail",
                placeholder="seu@email.com",
                autocomplete="email",
            )
            senha = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha",
                autocomplete="current-password",
            )
            enviado = st.form_submit_button(
                "Entrar no painel", type="primary", use_container_width=True
            )
        st.markdown(
            '<div class="login-rodape">Sessão protegida e encerrada após 30 minutos de inatividade.</div>',
            unsafe_allow_html=True,
        )

    return enviado, email, senha
