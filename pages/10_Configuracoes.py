"""Configurações: multa, juros, carência, limites de alerta, backup manual."""

import streamlit as st

from src.services import configuracoes
from src.domain.valores import decimal_br, hoje_br
from src.ui.componentes import cabecalho, proteger, sucesso

cabecalho("Configurações")
with proteger():
    config = configuracoes.obter()
    with st.form("configuracoes"):
        multa = st.text_input(
            "Multa por atraso (%)", str(config["multa_atraso_percentual"])
        )
        juros = st.text_input(
            "Juros ao mês (%)", str(config["juros_mensal_percentual"])
        )
        dados = {}
        for campo, titulo in [
            ("carencia_dias", "Carência em dias"),
            ("alerta_manutencao_km", "Alerta de manutenção (km)"),
            ("alerta_manutencao_dias", "Alerta de manutenção (dias)"),
            ("alerta_documento_dias", "Alerta de documentos (dias)"),
            ("alerta_cnh_dias", "Alerta de CNH (dias)"),
        ]:
            dados[campo] = st.number_input(
                titulo, min_value=0, value=config[campo], step=1
            )
        if st.form_submit_button("Salvar configurações", type="primary"):
            dados.update(
                multa_atraso_percentual=str(decimal_br(multa)),
                juros_mensal_percentual=str(decimal_br(juros)),
            )
            configuracoes.atualizar(dados)
            sucesso()
    st.subheader("Backup manual")
    st.caption(
        "ZIP com CSV das 14 tabelas. Contém dados pessoais; guarde em local privado. Fotos e comprovantes devem ser copiados separadamente do Storage. Evite outras alterações durante a geração."
    )
    if st.button("Gerar backup"):
        with st.spinner("Preparando os arquivos…"):
            arquivo = configuracoes.backup()
        st.download_button(
            "Baixar backup", arquivo, f"backup-{hoje_br()}.zip", "application/zip"
        )
