"""Aba "Portal" da ficha do cliente: vínculo do acesso do locatário e trocas de óleo."""

import streamlit as st

from src.services import portal_locatario
from src.ui.componentes import proteger, selo_situacao, sucesso, tabela_html
from src.ui.formatadores import formatar_data


def _km(valor):
    return f"{valor:,} km".replace(",", ".")


def _acesso(cliente):
    if cliente.get("auth_user_id"):
        st.success("Este cliente tem acesso ao portal do locatário.")
        if st.button("Remover acesso ao portal", key="desvincular_portal"):
            with proteger():
                portal_locatario.desvincular_acesso(cliente["id"])
                sucesso()
        return

    st.info(
        "Para liberar o portal: 1) crie o usuário (e-mail e senha) em Authentication > Users "
        "no painel do Supabase; 2) informe aqui o mesmo e-mail para vinculá-lo a este cliente."
    )
    with st.form("vincular_portal", border=False):
        email = st.text_input("E-mail do usuário criado no Supabase", cliente.get("email") or "")
        if st.form_submit_button("Vincular acesso", type="primary"):
            with proteger():
                portal_locatario.vincular_acesso(cliente["id"], email)
                sucesso()


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
