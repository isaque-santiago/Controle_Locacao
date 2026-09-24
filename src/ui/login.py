"""Tela de acesso do proprietário. A aparência (incluindo o modo escuro) vem do
design system: seção LOGIN de src/ui/estilos.css."""

import streamlit as st


def exibir() -> tuple[bool, str, str]:
    """Renderiza a tela de login e devolve envio, e-mail e senha."""
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
