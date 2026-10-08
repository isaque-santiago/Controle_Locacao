"""Aba "Portal" da ficha do cliente: acesso do locatário (CPF + senha) e trocas de óleo."""

import streamlit as st

from src.domain import mensagens
from src.services import portal_locatario
from src.ui import feedback
from src.ui.componentes import proteger, selo_situacao, tabela_html
from src.domain.formatadores import formatar_data

_CHAVE_CREDENCIAIS = "portal_credenciais_geradas"


def _km(valor):
    return f"{valor:,} km".replace(",", ".")


def _mostrar_credenciais(cliente):
    """Mostra as credenciais recém-geradas deste cliente até o dono fechar o aviso."""
    gerada = st.session_state.get(_CHAVE_CREDENCIAIS)
    if not gerada or gerada["cliente_id"] != cliente["id"]:
        return False
    st.warning(
        "Anote a senha agora: ela não é gravada no sistema e some quando você fechar este "
        "aviso ou sair. Entregue ao locatário o **CPF** e a senha; ele pode trocá-la no "
        "portal se quiser."
    )
    st.code(gerada["email"], language=None)
    st.code(gerada["senha"], language=None)
    if st.button("Fechar", key="fechar_credenciais_portal"):
        st.session_state.pop(_CHAVE_CREDENCIAIS, None)
        st.rerun()
    return True


def _guardar(cliente, credenciais):
    st.session_state[_CHAVE_CREDENCIAIS] = {"cliente_id": cliente["id"], **credenciais}
    st.rerun()


def _acesso(cliente):
    if _mostrar_credenciais(cliente):
        return

    if not cliente.get("auth_user_id"):
        st.info(
            "Este cliente ainda não tem acesso ao portal. O login dele será o CPF, com uma "
            "senha individual gerada aqui."
        )
        if st.button("Criar acesso", type="primary", key="ocupa_criar_acesso_portal"):
            with proteger():
                _guardar(cliente, portal_locatario.criar_acesso(cliente["id"]))
        return

    st.success("Acesso ativo ao portal do locatário.")
    with st.container(key="portal_acoes"):
        if st.button("Gerar nova senha", key="ocupa_nova_senha_portal"):
            with proteger():
                _guardar(cliente, portal_locatario.redefinir_senha(cliente["id"]))
        with st.popover("Remover acesso"):
            st.write("O login do locatário será excluído e ele deixará de entrar no portal.")
            if st.button("Confirmar remoção", key="ocupa_remover_acesso_portal", type="primary"):
                with proteger():
                    portal_locatario.remover_acesso(cliente["id"])
                    feedback.concluir(mensagens.acesso_portal_removido(cliente["nome"]))


def _trocas(cliente):
    trocas = sorted(
        portal_locatario.listar_trocas(cliente["id"]),
        key=lambda t: t["criado_em"],
        reverse=True,
    )
    st.markdown(
        '<h3 class="rotulo secao-titulo">Trocas de óleo reportadas</h3>',
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
        legenda="Trocas de óleo reportadas",
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
