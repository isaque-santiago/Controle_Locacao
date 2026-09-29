"""Portal do locatário (Fase 7): tela simples, pensada para o celular.

O locatário vê só o(s) contrato(s) ativo(s) dele e reporta a troca de óleo com a
foto do painel (hodômetro) e a nota fiscal do óleo (cláusula 4.13 do contrato).
"""

from datetime import date
from decimal import Decimal
from html import escape

import streamlit as st

from src.domain.manutencao_regras import calcular_proxima_manutencao, calcular_situacao
from src.domain.valores import hoje_br
from src.services import portal_locatario
from src.ui.componentes import cabecalho, cabecalho_pagina, chip_placa, proteger, selo_situacao
from src.ui.formatadores import formatar_data, formatar_moeda

_ROTULO_SITUACAO = {
    "em_dia": "Óleo em dia",
    "proxima": "Troca de óleo próxima",
    "vencida": "Troca de óleo vencida",
}


def _km(valor):
    return "—" if valor is None else f"{valor:,}".replace(",", ".") + " km"


def _situacao(contrato, dados):
    ultima_data = contrato.get("ultima_data")
    previsto = calcular_proxima_manutencao(
        contrato.get("ultima_km"),
        contrato.get("intervalo_km"),
        date.fromisoformat(ultima_data[:10]) if ultima_data else None,
        contrato.get("intervalo_dias"),
    )
    situacao = calcular_situacao(
        contrato["km_atual"],
        previsto["proxima_km"],
        hoje_br(),
        previsto["proxima_data"],
        dados["alerta_km"],
        dados["alerta_dias"],
    )
    return situacao, previsto


def _resumo(contrato, dados):
    situacao, previsto = _situacao(contrato, dados)
    proxima_km = previsto["proxima_km"]
    restantes = (
        _km(proxima_km - contrato["km_atual"])
        if proxima_km is not None and proxima_km >= contrato["km_atual"]
        else "—"
    )
    st.markdown(
        f"""
        <div class="cartao">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
            <div>{chip_placa(contrato["placa"], "grande")}
              <span class="texto-2" style="margin-left:8px;">{escape(contrato["modelo"])}</span></div>
            {selo_situacao(_ROTULO_SITUACAO[situacao], situacao)}
          </div>
          <div class="grade-dados grade-dados--duas" style="margin-top:14px;">
            <div class="campo"><span class="texto-2">Hodômetro registrado</span><span class="mono">{_km(contrato["km_atual"])}</span></div>
            <div class="campo"><span class="texto-2">Última troca de óleo</span><span class="mono">{_km(contrato.get("ultima_km"))}</span></div>
            <div class="campo"><span class="texto-2">Próxima troca em</span><span class="mono">{_km(proxima_km)}</span></div>
            <div class="campo"><span class="texto-2">Faltam</span><span class="mono">{restantes}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return previsto


def _historico(contrato):
    trocas = contrato.get("trocas") or []
    if not trocas:
        return
    with st.expander("Últimas trocas reportadas"):
        for troca in trocas:
            multa = " · multa aplicada" if troca["multada"] else ""
            st.write(
                f"{formatar_data(troca['criado_em'])} — {_km(troca['km'])}" + multa
            )


def _formulario(dados, contrato, previsto):
    multa = Decimal(str(dados["multa_valor"]))
    if multa > 0 and previsto["proxima_km"] is not None:
        st.info(
            f"A troca deve ser feita até **{_km(previsto['proxima_km'])}**. "
            + f"Se passar disso, é cobrada uma multa fixa de **{formatar_moeda(multa)}**."
        )

    chave = f"troca_oleo_{contrato['contrato_id']}"
    with st.form(chave, clear_on_submit=True):
        km = st.text_input("Hodômetro atual (km)", placeholder="Ex.: 12500")
        foto = st.file_uploader(
            "Foto do painel (mostrando o hodômetro)", type=["jpg", "jpeg", "png"]
        )
        nota = st.file_uploader("Foto da nota fiscal do óleo", type=["jpg", "jpeg", "png"])
        enviar = st.form_submit_button(
            "Enviar troca de óleo", type="primary", use_container_width=True
        )

    if not enviar:
        return
    if foto is None or nota is None:
        st.error("Anexe a foto do painel e a foto da nota fiscal.")
        return

    with st.spinner("Enviando…"):
        resultado = portal_locatario.registrar_troca_oleo(
            dados["cliente_id"],
            contrato,
            km,
            (foto.name, foto.getvalue()),
            (nota.name, nota.getvalue()),
            multa,
        )
    if resultado.get("excedeu"):
        valor = resultado.get("multa_valor")
        aviso = (
            f" Foi gerada uma cobrança de multa de {formatar_moeda(valor)}."
            if valor
            else " O proprietário foi avisado do atraso."
        )
        st.session_state["mensagem_sucesso"] = (
            "Troca registrada, mas passou do intervalo previsto." + aviso
        )
    else:
        st.session_state["mensagem_sucesso"] = "Troca de óleo registrada. Obrigado!"
    st.rerun()


def _alterar_senha():
    """Opcional: o locatário pode trocar a senha gerada por uma própria."""
    with st.expander("Alterar minha senha (opcional)"):
        with st.form("trocar_senha", clear_on_submit=True):
            nova = st.text_input("Nova senha", type="password", autocomplete="new-password")
            confirmacao = st.text_input(
                "Repita a nova senha", type="password", autocomplete="new-password"
            )
            st.caption("Mínimo de 8 caracteres, misturando letras e números; não use o seu CPF.")
            enviar = st.form_submit_button("Salvar nova senha", use_container_width=True)
        if enviar:
            portal_locatario.trocar_senha(nova, confirmacao)
            st.success("Senha alterada. Use a nova senha no próximo acesso.")


def exibir():
    cabecalho("Portal do locatário", exibir_titulo=False)
    with proteger():
        dados = portal_locatario.dados_portal()
        cabecalho_pagina(
            f"Olá, {dados['nome'].split()[0]}",
            sub="Registre aqui a troca de óleo da sua moto.",
        )
        if not dados["contratos"]:
            st.info("Você não tem contrato ativo no momento.")
            _alterar_senha()
            return
        for contrato in dados["contratos"]:
            previsto = _resumo(contrato, dados)
            if contrato.get("intervalo_km") is None and contrato.get("ultima_km") is None:
                st.warning(
                    "O plano de troca de óleo desta moto ainda não foi configurado. "
                    "Fale com o proprietário."
                )
                continue
            _formulario(dados, contrato, previsto)
            _historico(contrato)
        _alterar_senha()
