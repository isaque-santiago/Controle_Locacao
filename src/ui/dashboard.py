"""Dashboard: faixa de instrumentos, Hoje e Alertas — segue Arquivos/Design_UI.md
e o artboard Main.dc.html do mockup (link na seção 1 do documento)."""

import streamlit as st

from src.services import dashboard, alertas, cobrancas, configuracoes, clientes, manutencao
from src.domain.valores import hoje_br
from src.ui.componentes import cabecalho, proteger
from src.ui.formatadores import formatar_data, formatar_moeda, formatar_moeda_compacta

_DIAS = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]
_MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def _data_por_extenso(data):
    return f"{_DIAS[data.weekday()]}, {data.day} de {_MESES[data.month - 1]} de {data.year}"


def _cabecalho_pagina():
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;justify-content:space-between;">
          <div>
            <h1 class="rotulo" style="margin:0;font-size:28px;color:#1E2227;">Dashboard</h1>
            <div style="color:#585F66;font-size:13px;margin-top:2px;">{_data_por_extenso(hoje_br())}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;color:#585F66;font-size:12px;">
            <span style="width:6px;height:6px;border-radius:50%;background:#2F9E6E;display:inline-block;"></span>
            Cobranças em dia atualizadas agora
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _faixa_instrumentos(dados, contagem, devedores_count, ordens_concluidas):
    frota_total = len(dados["frota"])
    ativas = sum(1 for m in dados["frota"] if m["status"] != "inativa")
    alugadas = contagem.get("alugada", 0)
    ocupacao = round(100 * alugadas / ativas) if ativas else 0
    total_base = max(frota_total, 1)
    larguras = {
        chave: round(100 * contagem.get(chave, 0) / total_base, 1)
        for chave in ("alugada", "disponivel", "manutencao", "inativa")
    }
    previsto = dados["previsto"]
    recebido = dados["recebido"]
    progresso_recebido = (
        min(100, round(100 * recebido / previsto)) if previsto else 0
    )

    segmentos = "".join(
        f'<div style="width:{largura}%;background:{cor};"></div>'
        for largura, cor in [
            (larguras["alugada"], "#1E2227"),
            (larguras["disponivel"], "#2F9E6E"),
            (larguras["manutencao"], "#F2B705"),
            (larguras["inativa"], "#9AA0A6"),
        ]
        if largura > 0
    )
    legenda = "".join(
        f'<div style="display:flex;align-items:center;gap:5px;font-size:12px;color:#585F66;">'
        f'<span style="width:8px;height:8px;background:{cor};border-radius:2px;display:inline-block;"></span>'
        f"{contagem.get(chave, 0)} {rotulo}</div>"
        for chave, rotulo, cor in [
            ("alugada", "alugadas", "#1E2227"),
            ("disponivel", "disponíveis", "#2F9E6E"),
            ("manutencao", "manutenção", "#F2B705"),
            ("inativa", "inativas", "#9AA0A6"),
        ]
    )

    st.markdown(
        f"""
        <div style="display:flex;background:#FAFAF9;border:1px solid rgba(30,34,39,0.12);border-radius:2px;">
          <div style="flex:1.3;padding:18px 24px;display:flex;flex-direction:column;gap:10px;border-right:1px solid rgba(30,34,39,0.12);">
            <div class="rotulo" style="font-size:12px;color:#585F66;letter-spacing:0.03em;">frota</div>
            <div style="display:flex;align-items:baseline;gap:8px;">
              <span class="mono" style="font-size:34px;font-weight:600;line-height:1;">{frota_total}</span>
              <span style="font-size:13px;color:#585F66;">motos · {ocupacao}% ocupação</span>
            </div>
            <div style="display:flex;height:8px;border-radius:2px;overflow:hidden;background:rgba(30,34,39,0.12);">{segmentos}</div>
            <div style="display:flex;gap:14px;flex-wrap:wrap;">{legenda}</div>
          </div>
          <div style="flex:1;padding:18px 24px;display:flex;flex-direction:column;gap:10px;border-right:1px solid rgba(30,34,39,0.12);">
            <div class="rotulo" style="font-size:12px;color:#585F66;letter-spacing:0.03em;">recebido no mês</div>
            <span class="mono" style="font-size:34px;font-weight:600;line-height:1;">{formatar_moeda_compacta(recebido)}</span>
            <div style="height:8px;border-radius:2px;background:rgba(30,34,39,0.12);overflow:hidden;">
              <div style="width:{progresso_recebido}%;height:100%;background:#2F9E6E;"></div>
            </div>
            <div style="font-size:12px;color:#585F66;">de {formatar_moeda_compacta(previsto)} previstos</div>
          </div>
          <div style="flex:1;padding:18px 24px;display:flex;flex-direction:column;gap:10px;border-right:1px solid rgba(30,34,39,0.12);">
            <div class="rotulo" style="font-size:12px;color:#585F66;letter-spacing:0.03em;">em atraso</div>
            <span class="mono" style="font-size:34px;font-weight:600;line-height:1;color:#D64545;">{formatar_moeda_compacta(dados["atrasado"])}</span>
            <div style="font-size:12px;color:#585F66;">{devedores_count} cliente(s) atrasado(s)</div>
          </div>
          <div style="flex:1;padding:18px 24px;display:flex;flex-direction:column;gap:10px;">
            <div class="rotulo" style="font-size:12px;color:#585F66;letter-spacing:0.03em;">manutenção no mês</div>
            <span class="mono" style="font-size:34px;font-weight:600;line-height:1;">{formatar_moeda_compacta(dados["manutencao"])}</span>
            <div style="font-size:12px;color:#585F66;">{ordens_concluidas} ordem(ns) concluída(s)</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


_COLUNAS_HOJE = [2, 1.3, 1.3, 1.1, 1.6, 0.5]


def _situacao_cobranca_html(cobranca):
    if cobranca["situacao"] == "atrasada":
        dias = max((hoje_br() - _iso_data(cobranca["vencimento"])).days, 0)
        texto = f"Atrasada há {dias} dia(s)"
        cor = "#D64545"
    else:
        texto = "Vence hoje"
        cor = "#F2B705"
    estilo_cor = f"color:{cor};" if cobranca["situacao"] == "atrasada" else ""
    return (
        f'<div style="display:flex;align-items:center;gap:6px;{estilo_cor}">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{cor};display:inline-block;"></span>{texto}</div>'
    )


def _iso_data(valor):
    from datetime import date

    return date.fromisoformat(str(valor)[:10])


def _cartao_hoje(cobrancas_hoje, placas, nomes):
    with st.container(key="dashboard_card_hoje"):
        st.markdown(
            """
            <div style="padding:16px 20px;border-bottom:1px solid rgba(30,34,39,0.12);display:flex;align-items:center;justify-content:space-between;">
              <h2 class="rotulo" style="margin:0;font-size:16px;">Hoje</h2>
              <span style="font-size:12px;color:#585F66;">vencendo hoje e atrasadas</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cab = st.columns(_COLUNAS_HOJE, vertical_alignment="center")
        for coluna, rotulo, direita in zip(
            cab,
            ["Cliente", "Moto", "Vencimento", "Valor", "Situação", ""],
            [False, False, False, True, False, False],
        ):
            alinhamento = "text-align:right;" if direita else ""
            coluna.markdown(
                f'<span style="font-size:13px;color:#585F66;{alinhamento}display:block;">{rotulo}</span>',
                unsafe_allow_html=True,
            )
        if not cobrancas_hoje:
            st.markdown(
                '<div style="padding:12px 20px;color:#585F66;font-size:13px;">Nenhuma cobrança vencendo hoje ou atrasada.</div>',
                unsafe_allow_html=True,
            )
        for c in cobrancas_hoje:
            linha = st.columns(_COLUNAS_HOJE, vertical_alignment="center")
            linha[0].markdown(
                f'<span style="font-size:13px;">{nomes.get(c["cliente_id"], "—")}</span>',
                unsafe_allow_html=True,
            )
            linha[1].markdown(
                f'<span class="mono" style="font-size:13px;color:#585F66;">{placas.get(c["moto_id"], "—")}</span>',
                unsafe_allow_html=True,
            )
            linha[2].markdown(
                f'<span class="mono" style="font-size:13px;">{formatar_data(c["vencimento"])}</span>',
                unsafe_allow_html=True,
            )
            linha[3].markdown(
                f'<span class="mono" style="font-size:13px;text-align:right;display:block;">{formatar_moeda(c["valor"])}</span>',
                unsafe_allow_html=True,
            )
            linha[4].markdown(_situacao_cobranca_html(c), unsafe_allow_html=True)
            if linha[5].button(
                "✓", key=f"pagar_hoje_{c['id']}", help="Registrar pagamento"
            ):
                st.session_state["cobranca_rapida"] = c["id"]
                st.switch_page("pages/5_Cobrancas.py")


def _item_alerta(numero, titulo, descricao, cor_borda, cor_numero):
    return f"""
        <div style="display:flex;align-items:center;gap:12px;">
          <div class="mono" style="width:40px;height:40px;border-radius:50%;border:2px dashed {cor_borda};color:{cor_numero};display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;flex-shrink:0;">{numero}</div>
          <div>
            <div style="font-size:13px;font-weight:500;">{titulo}</div>
            <div style="font-size:12px;color:#585F66;">{descricao}</div>
          </div>
        </div>
        """


def _cartao_alertas(dados_config, alertas_manutencao, alertas_documentos, alertas_cnh):
    itens = []

    vencidas = [a for a in alertas_manutencao if a["situacao"] == "vencida"]
    if vencidas:
        nomes = ", ".join(dict.fromkeys(a["item"] for a in vencidas[:2]))
        if len(vencidas) > 2:
            nomes += f" e mais {len(vencidas) - 2}"
        itens.append(_item_alerta(len(vencidas), "Manutenção vencida", nomes, "#D64545", "#D64545"))

    proximas = [a for a in alertas_manutencao if a["situacao"] == "proxima"]
    if proximas:
        descricao = (
            f"nos próximos {dados_config['alerta_manutencao_km']} km ou "
            f"{dados_config['alerta_manutencao_dias']} dias"
        )
        itens.append(_item_alerta(len(proximas), "Manutenção próxima", descricao, "#F2B705", "#8a6600"))

    doc_vencidos = [a for a in alertas_documentos if a["situacao"] == "vencido"]
    if doc_vencidos:
        primeiro = doc_vencidos[0]
        descricao = f"{primeiro['tipo'].upper()} · moto {primeiro['placa']}"
        if len(doc_vencidos) > 1:
            descricao += f" e mais {len(doc_vencidos) - 1}"
        itens.append(_item_alerta(len(doc_vencidos), "Documento vencido", descricao, "#D64545", "#D64545"))

    doc_a_vencer = [a for a in alertas_documentos if a["situacao"] == "a_vencer"]
    if doc_a_vencer:
        descricao = f"próximos {dados_config['alerta_documento_dias']} dias"
        itens.append(_item_alerta(len(doc_a_vencer), "Documento a vencer", descricao, "#F2B705", "#8a6600"))

    cnh_vencidas = [a for a in alertas_cnh if a["situacao"] == "vencida"]
    if cnh_vencidas:
        primeiro = cnh_vencidas[0]
        descricao = f"{primeiro['nome']} · {formatar_data(primeiro['cnh_validade'])}"
        if len(cnh_vencidas) > 1:
            descricao += f" e mais {len(cnh_vencidas) - 1}"
        itens.append(_item_alerta(len(cnh_vencidas), "CNH vencida", descricao, "#D64545", "#D64545"))

    cnh_a_vencer = [a for a in alertas_cnh if a["situacao"] == "a_vencer"]
    if cnh_a_vencer:
        primeiro = cnh_a_vencer[0]
        descricao = f"{primeiro['nome']} · {formatar_data(primeiro['cnh_validade'])}"
        if len(cnh_a_vencer) > 1:
            descricao += f" e mais {len(cnh_a_vencer) - 1}"
        itens.append(_item_alerta(len(cnh_a_vencer), "CNH a vencer", descricao, "#F2B705", "#8a6600"))

    corpo = (
        '<div style="padding:16px 20px;display:flex;flex-direction:column;gap:16px;">'
        + "".join(itens)
        + "</div>"
        if itens
        else '<div style="padding:16px 20px;color:#585F66;font-size:13px;">Nenhum alerta no momento.</div>'
    )
    st.markdown(
        f"""
        <div style="background:#FAFAF9;border:1px solid rgba(30,34,39,0.12);border-radius:2px;">
          <div style="padding:16px 20px;border-bottom:1px solid rgba(30,34,39,0.12);">
            <h2 class="rotulo" style="margin:0;font-size:16px;">Alertas</h2>
          </div>
          {corpo}
        </div>
        """,
        unsafe_allow_html=True,
    )


def exibir():
    cabecalho("Dashboard", exibir_titulo=False)
    with proteger():
        cobrancas.gerar_cobrancas_pendentes()
        dados = dashboard.resumo()
        frota = dados["frota"]
        contagem = {
            status: sum(1 for m in frota if m["status"] == status)
            for status in ("disponivel", "alugada", "manutencao", "inativa")
        }
        hoje_iso = hoje_br().isoformat()
        cobrancas_hoje = [
            c
            for c in dados["cobrancas"]
            if c["situacao"] == "atrasada"
            or (c["situacao"] == "aberta" and c["vencimento"] == hoje_iso)
        ]
        cobrancas_hoje.sort(key=lambda c: c["vencimento"])
        placas = {m["id"]: m["placa"] for m in frota}
        mes_atual = hoje_iso[:7]
        ordens_concluidas = sum(
            1
            for m in manutencao.listar_manutencoes()
            if m["status"] == "concluida" and m["data_entrada"][:7] == mes_atual
        )
        nomes = {c["id"]: c["nome"] for c in clientes.listar()}

        _cabecalho_pagina()
        st.write("")
        _faixa_instrumentos(dados, contagem, len(dados["devedores"]), ordens_concluidas)
        st.write("")
        col_hoje, col_alertas = st.columns([1.6, 1], gap="medium")
        with col_hoje:
            _cartao_hoje(cobrancas_hoje, placas, nomes)
        with col_alertas:
            _cartao_alertas(
                configuracoes.obter(),
                alertas.listar_manutencao(),
                alertas.listar_documentos(),
                alertas.listar_cnh(),
            )
