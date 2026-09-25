"""Configurações: encargos, alertas e backup manual — segue Configuracoes.dc.html
do mockup (cartões em largura total, exemplo de cálculo, backup em ZIP)."""

from decimal import Decimal
from html import escape

import streamlit as st

from src.domain.configuracoes import exemplo_encargos
from src.domain.valores import hoje_br
from src.services import configuracoes
from src.ui.componentes import cabecalho, proteger, sucesso
from src.ui.formatadores import formatar_moeda


def _percentual(valor):
    return f"{Decimal(str(valor)):.2f}".replace(".", ",")


def _titulo_cartao(titulo, descricao):
    st.markdown(
        f"""
        <h3 class="rotulo" style="margin:0 0 4px 0;font-size:15px;color:var(--texto);">{escape(titulo)}</h3>
        <div style="font-size:var(--fs-legenda);color:var(--texto-2);margin-bottom:14px;">{escape(descricao)}</div>
        """,
        unsafe_allow_html=True,
    )


def _mono(texto, forte=False):
    peso = "font-weight:600;" if forte else ""
    return f'<span class="mono" style="color:var(--texto);{peso}">{escape(texto)}</span>'


def _exemplo(multa, juros, carencia):
    """Cálculo com os valores hoje salvos (o formulário só grava ao salvar)."""
    e = exemplo_encargos(multa, juros, carencia)
    st.markdown(
        '<div style="background:var(--fundo);border-radius:var(--raio-sm);padding:12px 16px;'
        'font-size:var(--fs-legenda);color:var(--texto-2);">Exemplo: cobrança de '
        f'{_mono(formatar_moeda(e["saldo"]))}, vencida há {_mono(str(e["dias_vencida"]) + " dias")} → '
        f'multa {_mono(formatar_moeda(e["multa"]))} + juros {_mono(formatar_moeda(e["juros"]))} = '
        f'total {_mono(formatar_moeda(e["total"]), True)}</div>',
        unsafe_allow_html=True,
    )


def _formulario(config):
    entrada = {}
    with st.form("configuracoes", border=False):
        titulo, acao = st.columns([5, 1], vertical_alignment="top")
        titulo.markdown(
            """
            <h1 class="rotulo pagina-titulo">Configurações</h1>
            <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">Parâmetros do sistema</div>
            """,
            unsafe_allow_html=True,
        )
        salvar = acao.form_submit_button(
            "Salvar alterações", type="primary", use_container_width=True
        )

        with st.container(key="config_card_encargos"):
            _titulo_cartao(
                "Encargos por atraso",
                "Aplicados sobre o saldo em aberto após a carência.",
            )
            c1, c2, c3 = st.columns(3)
            entrada["multa_atraso_percentual"] = c1.text_input(
                "Multa por atraso (%)", _percentual(config["multa_atraso_percentual"])
            )
            entrada["juros_mensal_percentual"] = c2.text_input(
                "Juros mensal (%)", _percentual(config["juros_mensal_percentual"])
            )
            entrada["carencia_dias"] = c3.text_input(
                "Carência (dias)", str(config["carencia_dias"])
            )
            _exemplo(
                config["multa_atraso_percentual"],
                config["juros_mensal_percentual"],
                config["carencia_dias"],
            )

        with st.container(key="config_card_manutencao"):
            _titulo_cartao(
                "Alertas de manutenção",
                'Quando um item entra em situação "próxima" antes de vencer.',
            )
            c1, c2 = st.columns(2)
            entrada["alerta_manutencao_km"] = c1.text_input(
                "Avisar (km antes)", str(config["alerta_manutencao_km"])
            )
            entrada["alerta_manutencao_dias"] = c2.text_input(
                "Avisar (dias antes)", str(config["alerta_manutencao_dias"])
            )

        with st.container(key="config_card_documentos"):
            _titulo_cartao(
                "Alertas de documentos e CNH",
                'Dias antes do vencimento para marcar como "a vencer".',
            )
            c1, c2 = st.columns(2)
            entrada["alerta_documento_dias"] = c1.text_input(
                "Documentos da moto (dias)", str(config["alerta_documento_dias"])
            )
            entrada["alerta_cnh_dias"] = c2.text_input(
                "CNH do cliente (dias)", str(config["alerta_cnh_dias"])
            )
    return salvar, entrada


def _backup():
    with st.container(key="config_card_backup"):
        _titulo_cartao(
            "Backup manual",
            "Gera um ZIP com um CSV de cada uma das 14 tabelas. Contém dados pessoais; "
            "guarde em local privado. Fotos e comprovantes devem ser copiados "
            "separadamente do Storage. Evite outras alterações durante a geração. "
            "Recomendado semanalmente.",
        )
        texto, acao = st.columns([3, 1.4], vertical_alignment="center")
        gerado = st.session_state.get("config_backup")
        if gerado:
            texto.markdown(
                '<div style="font-size:var(--fs-legenda);color:var(--texto-2);">Backup desta sessão: '
                f'{_mono(gerado["quando"])}</div>',
                unsafe_allow_html=True,
            )
            acao.download_button(
                "Baixar backup",
                gerado["arquivo"],
                f"backup-{gerado['data']}.zip",
                "application/zip",
                type="primary",
                use_container_width=True,
            )
        else:
            texto.markdown(
                '<div style="font-size:var(--fs-legenda);color:var(--texto-2);">Nenhum backup gerado nesta sessão.</div>',
                unsafe_allow_html=True,
            )
            if acao.button("Gerar backup", use_container_width=True):
                with st.spinner("Preparando os arquivos…"):
                    arquivo = configuracoes.backup()
                hoje = hoje_br()
                st.session_state["config_backup"] = {
                    "arquivo": arquivo,
                    "data": hoje.isoformat(),
                    "quando": hoje.strftime("%d/%m/%Y"),
                }
                st.rerun()


def exibir():
    cabecalho("Configurações", exibir_titulo=False)
    with proteger(), st.container(key="config_pagina"):
        config = configuracoes.obter()
        salvar, entrada = _formulario(config)
        if salvar:
            configuracoes.atualizar(entrada)
            sucesso()
        _backup()
