"""Configurações: encargos, alertas e backup manual — segue Configuracoes.dc.html
do mockup (cartões em largura total, exemplo de cálculo, backup em ZIP)."""

from html import escape

import streamlit as st

from src.domain import mensagens
from src.domain.configuracoes import LIMITE_INTEIRO as _LIMITE, campos_alterados, exemplo_encargos
from src.domain.valores import hoje_br
from src.services import configuracoes
from src.ui import feedback
from src.ui.componentes import cabecalho, cabecalho_pagina, proteger
from src.domain.formatadores import formatar_moeda
from src.ui.formularios import campo_inteiro, campo_moeda, linha_campos


def _titulo_cartao(titulo, descricao):
    st.markdown(
        f"""
        <h2 class="rotulo config-titulo">{escape(titulo)}</h2>
        <div class="config-descricao">{escape(descricao)}</div>
        """,
        unsafe_allow_html=True,
    )


def _mono(texto, forte=False):
    return f'<span class="mono texto-forte{" texto-negrito" if forte else ""}">{escape(texto)}</span>'


def _exemplo(multa, adicional_diario):
    """Cálculo com os valores hoje salvos (o formulário só grava ao salvar)."""
    e = exemplo_encargos(multa, adicional_diario)
    st.markdown(
        '<div class="config-exemplo">Exemplo: locação de '
        f'{_mono(formatar_moeda(e["saldo"]))}, vencida há {_mono(str(e["dias_vencida"]) + " dias")} → '
        f'multa {_mono(formatar_moeda(e["multa"]))} + adicional {_mono(formatar_moeda(e["adicional_diario"]))} = '
        f'total {_mono(formatar_moeda(e["total"]), True)}</div>',
        unsafe_allow_html=True,
    )


def _formulario(config):
    entrada = {}
    with st.form("configuracoes", border=False):
        salvar = cabecalho_pagina(
            "Configurações",
            sub="Parâmetros do sistema",
            acao={
                "rotulo": "Salvar alterações",
                "chave": "ocupa_configuracoes_salvar",
                "icone": ":material/save:",
                "formulario": True,
            },
        )

        with st.container(key="config_card_encargos"):
            _titulo_cartao(
                "Encargos por atraso",
                "Valores fixos cobrados das locações em atraso, sem carência: a multa já no dia do "
                "vencimento e o adicional a cada dia depois dele.",
            )
            with linha_campos([1, 1], "cfg_encargos") as (c1, c2):
                with c1:
                    entrada["multa_atraso_valor"] = campo_moeda(
                        "Multa de atraso (no vencimento)", config["multa_atraso_valor"], "cfg_multa"
                    )
                with c2:
                    entrada["encargo_diario_valor"] = campo_moeda(
                        "Adicional por dia de atraso", config["encargo_diario_valor"], "cfg_adicional_diario"
                    )
            _exemplo(config["multa_atraso_valor"], config["encargo_diario_valor"])

        with st.container(key="config_card_manutencao"):
            _titulo_cartao(
                "Alertas de manutenção",
                'Quando um item entra em situação "próxima" antes de vencer.',
            )
            with linha_campos([1, 1], "cfg_manutencao") as (c1, c2):
                with c1:
                    entrada["alerta_manutencao_km"] = campo_inteiro(
                        "Avisar antes", config["alerta_manutencao_km"], "cfg_alerta_km", sufixo="km", maximo=_LIMITE
                    )
                with c2:
                    entrada["alerta_manutencao_dias"] = campo_inteiro(
                        "Avisar antes", config["alerta_manutencao_dias"], "cfg_alerta_dias", sufixo="dias", maximo=_LIMITE
                    )
            entrada["multa_troca_oleo_valor"] = campo_moeda(
                "Multa por troca de óleo fora do intervalo",
                config.get("multa_troca_oleo_valor") or 0,
                "cfg_multa_oleo",
                ajuda="Valor fixo cobrado do locatário quando ele reporta a troca de óleo "
                "depois do intervalo do plano. Deixe 0,00 para não cobrar multa.",
            )

        with st.container(key="config_card_documentos"):
            _titulo_cartao(
                "Alertas de documentos e CNH",
                'Dias antes do vencimento para marcar como "a vencer".',
            )
            with linha_campos([1, 1], "cfg_documentos") as (c1, c2):
                with c1:
                    entrada["alerta_documento_dias"] = campo_inteiro(
                        "Documentos da moto", config["alerta_documento_dias"], "cfg_alerta_doc", sufixo="dias", maximo=_LIMITE
                    )
                with c2:
                    entrada["alerta_cnh_dias"] = campo_inteiro(
                        "CNH do cliente", config["alerta_cnh_dias"], "cfg_alerta_cnh", sufixo="dias", maximo=_LIMITE
                    )
    return salvar, entrada


def _backup():
    with st.container(key="config_card_backup"):
        _titulo_cartao(
            "Backup manual",
            "Gera um ZIP com um CSV de cada uma das 15 tabelas. Contém dados pessoais; "
            "guarde em local privado. Fotos e comprovantes devem ser copiados "
            "separadamente do Storage. Evite outras alterações durante a geração. "
            "Recomendado semanalmente.",
        )
        texto, acao = st.columns([3, 1.4], vertical_alignment="center")
        gerado = st.session_state.get("config_backup")
        if gerado:
            texto.markdown(
                '<div class="fs-legenda texto-2">Backup desta sessão: '
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
                '<div class="fs-legenda texto-2">Nenhum backup gerado nesta sessão.</div>',
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
    with proteger(nova_tentativa=True), st.container(key="config_pagina"):
        config = configuracoes.obter()
        salvar, entrada = _formulario(config)
        if salvar:
            with proteger():
                novos = configuracoes.atualizar(entrada)
                feedback.concluir(mensagens.configuracoes_salvas(campos_alterados(config, novos)))
        _backup()
