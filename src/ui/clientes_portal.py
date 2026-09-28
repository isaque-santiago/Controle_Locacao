"""Aba "Portal" da ficha do cliente: acesso do locatário (CPF + senha) e trocas de óleo."""

import streamlit as st

from src.services import portal_locatario
from src.ui.componentes import proteger, selo_situacao, sucesso, tabela_html
from src.ui.formatadores import formatar_data

_CHAVE_CREDENCIAIS = "portal_credenciais_geradas"


def _km(valor):
    return f"{valor:,} km".replace(",", ".")


def _credenciais(cliente):
    """Devolve as credenciais geradas para este cliente (mostradas até confirmar/fechar)."""
    gerada = st.session_state.get(_CHAVE_CREDENCIAIS)
    if not gerada or gerada["cliente_id"] != cliente["id"]:
        return None
    if gerada.get("nova_senha"):
        instrucao = (
            "No painel do Supabase (Authentication > Users), abra este usuário e defina "
            "a senha abaixo (Reset password / Update user)."
        )
    else:
        instrucao = (
            "No painel do Supabase (Authentication > Users > Add user), crie o usuário com o "
            "e-mail e a senha abaixo e marque **Auto Confirm User**. Depois clique em "
            "**Confirmar e vincular**."
        )
    st.warning(
        "Anote a senha agora: ela não é gravada no banco e some quando você fechar ou sair. "
        + instrucao
        + " Entregue ao locatário o CPF e a senha; ele pode trocá-la no portal se quiser."
    )
    st.code(gerada["email"], language=None)
    st.code(gerada["senha"], language=None)
    return gerada


def _gerar(cliente, **extras):
    with proteger():
        credenciais = portal_locatario.gerar_credenciais(cliente.get("cpf") or "")
        st.session_state[_CHAVE_CREDENCIAIS] = {"cliente_id": cliente["id"], **credenciais, **extras}
        st.rerun()


def _fechar():
    st.session_state.pop(_CHAVE_CREDENCIAIS, None)
    st.rerun()


def _acesso(cliente):
    gerada = _credenciais(cliente)

    if cliente.get("auth_user_id"):
        if gerada:
            if st.button("Fechar", key="fechar_credenciais_portal"):
                _fechar()
            return
        st.success("Acesso ativo ao portal do locatário.")
        col_nova, col_remover = st.columns(2)
        if col_nova.button("Gerar nova senha", key="nova_senha_portal", use_container_width=True):
            _gerar(cliente, nova_senha=True)
        if col_remover.button("Remover acesso ao portal", key="desvincular_portal", use_container_width=True):
            with proteger():
                portal_locatario.desvincular_acesso(cliente["id"])
                sucesso()
        return

    if gerada:
        with proteger():
            if st.button("Confirmar e vincular", type="primary", key="confirmar_vinculo_portal"):
                portal_locatario.vincular_acesso(cliente["id"])
                st.session_state.pop(_CHAVE_CREDENCIAIS, None)
                sucesso()
        if st.button("Cancelar", key="cancelar_credenciais_portal"):
            _fechar()
        return

    st.info(
        "Este cliente ainda não tem acesso ao portal. O login dele será o CPF, com uma "
        "senha individual gerada aqui."
    )
    if st.button("Gerar senha de acesso", type="primary", key="gerar_credenciais_portal"):
        _gerar(cliente)


def _trocas(cliente):
    trocas = sorted(
        portal_locatario.listar_trocas(cliente["id"]),
        key=lambda t: t["criado_em"],
        reverse=True,
    )
    st.markdown(
        '<h3 class="rotulo" style="font-size:14px;">Trocas de óleo reportadas</h3>',
        unsafe_allow_html=True,
    )
    tabela_html(
        ["Data", "Hodômetro", "Acima do previsto", "Multa"],
        [
            [
                f'<span class="mono">{formatar_data(t["criado_em"])}</span>',
                f'<span class="mono">{_km(t["km"])}</span>',
                f'<span class="mono">{_km(t["km_excedente"])}</span>' if t["km_excedente"] else "—",
                selo_situacao("Cobrada", "vencida") if t["cobranca_id"] else "—",
            ]
            for t in trocas
        ],
    )
    if not trocas:
        return
    escolhida = st.selectbox(
        "Ver fotos da troca",
        trocas,
        format_func=lambda t: f'{formatar_data(t["criado_em"])} — {_km(t["km"])}',
        key="portal_troca_escolhida",
    )
    with proteger():
        st.link_button("Foto do painel", portal_locatario.url_arquivo(escolhida["foto_painel_path"]))
        st.link_button("Nota fiscal", portal_locatario.url_arquivo(escolhida["nota_fiscal_path"]))


def aba_portal(cliente):
    _acesso(cliente)
    _trocas(cliente)
