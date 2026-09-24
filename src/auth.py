"""Login, logout e guarda de página (require_login)."""

import streamlit as st
from time import time
from supabase_auth.errors import AuthApiError

from src.db import (
    clear_session_tokens,
    get_client,
    get_refresh_token_cookie,
    marcar_atividade_cookie,
    salvar_tema_escuro_cookie,
    sessao_ativa_no_cookie,
    set_session_tokens,
    sincronizar_refresh_token_cookie,
)
from src.ui import tema

_CHAVE_USUARIO = "usuario"


def esta_autenticado() -> bool:
    return _CHAVE_USUARIO in st.session_state


def login(email: str, senha: str) -> None:
    """Autentica no Supabase e guarda o usuário e os tokens na sessão."""
    resposta = get_client().auth.sign_in_with_password(
        {"email": email, "password": senha}
    )
    set_session_tokens(resposta.session.access_token, resposta.session.refresh_token)
    st.session_state[_CHAVE_USUARIO] = {
        "id": resposta.user.id,
        "email": resposta.user.email,
    }
    st.session_state["ultima_atividade"] = time()
    marcar_atividade_cookie()


def logout() -> None:
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    clear_session_tokens()
    for chave in list(st.session_state):
        del st.session_state[chave]


def _tentar_restaurar_sessao() -> bool:
    """Restaura a sessão a partir do cookie do navegador após um refresh."""
    refresh_token = get_refresh_token_cookie()
    if not refresh_token or not sessao_ativa_no_cookie():
        clear_session_tokens()
        return False
    try:
        resposta = get_client().auth.refresh_session(refresh_token)
    except Exception:
        clear_session_tokens()
        return False
    if not resposta.session or not resposta.user:
        clear_session_tokens()
        return False
    set_session_tokens(resposta.session.access_token, resposta.session.refresh_token)
    st.session_state[_CHAVE_USUARIO] = {
        "id": resposta.user.id,
        "email": resposta.user.email,
    }
    st.session_state["ultima_atividade"] = time()
    marcar_atividade_cookie()
    return True


def _exibir_formulario_login() -> None:
    """Mostra o login. Ao autenticar, esvazia o formulário e segue a MESMA execução
    (sem st.rerun): um rerun imediato descartaria o componente que grava o cookie
    antes de o navegador executá-lo, e o F5 voltaria ao login."""
    from src.ui.login import exibir

    espaco = st.empty()
    with espaco.container():
        enviado, email, senha = exibir()

    if enviado:
        if not email.strip() or not senha:
            st.error("Informe o e-mail e a senha.")
            return
        try:
            login(email.strip(), senha)
            espaco.empty()
        except AuthApiError:
            st.error("E-mail ou senha inválidos.")
        except (RuntimeError, KeyError) as erro:
            st.error(f"O aplicativo não está configurado: {erro}")
        except Exception:
            st.error(
                "Não foi possível acessar o Supabase. Confira os segredos do "
                "aplicativo e tente novamente."
            )


def _salvar_tema_escuro() -> None:
    """Guarda a escolha do toggle na sessão e no cookie do navegador."""
    escuro = st.session_state["modo_escuro"]
    st.session_state["tema_escuro"] = escuro
    salvar_tema_escuro_cookie(escuro)


def _usar_tema_do_sistema() -> None:
    """Volta ao modo automático (acompanha o tema do sistema)."""
    st.session_state["tema_escuro"] = None
    st.session_state.pop("modo_escuro", None)
    salvar_tema_escuro_cookie(None)


def require_login() -> None:
    """Bloqueia a página até o dono estar autenticado; exibe login se não estiver."""
    if not esta_autenticado():
        _tentar_restaurar_sessao()

    if (
        esta_autenticado()
        and time() - st.session_state.get("ultima_atividade", 0) > 1800
    ):
        logout()
        st.info("A sessão expirou por inatividade. Entre novamente.")
    if not esta_autenticado():
        _exibir_formulario_login()
        st.stop()

    st.session_state["ultima_atividade"] = time()
    marcar_atividade_cookie()
    sincronizar_refresh_token_cookie()

    email = st.session_state[_CHAVE_USUARIO]["email"]
    nome = email.split("@")[0].replace(".", " ").replace("_", " ").title() or email
    inicial = nome[0].upper()

    with st.sidebar:
        # A escolha fica em "tema_escuro" (chave que não é de widget), pois o estado
        # do toggle é descartado pelo Streamlit na troca de página.
        st.toggle(
            "Modo escuro",
            key="modo_escuro",
            value=tema.tema_escuro_ativo(),
            on_change=_salvar_tema_escuro,
        )
        if st.session_state.get("tema_escuro") is not None:
            st.button(
                "Usar tema do sistema",
                key="botao_tema_sistema",
                type="tertiary",
                on_click=_usar_tema_do_sistema,
            )
        with st.container(key="dashboard_sidebar_rodape"):
            col_perfil, col_sair = st.columns([1.6, 1], vertical_alignment="center")
            col_perfil.markdown(
                f"""
                <div class="usuario-lateral">
                  <div class="usuario-lateral__avatar">{inicial}</div>
                  <div class="usuario-lateral__nome">{nome}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if col_sair.button("Sair", key="botao_sair", use_container_width=True):
                logout()
                st.rerun()
