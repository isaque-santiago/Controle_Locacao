"""Dashboard: faixa de indicadores, Hoje e Alertas — segue Arquivos/Design_UI.md
e o artboard Main.dc.html do mockup (link na seção 1 do documento)."""

from html import escape

import streamlit as st

from src.services import dashboard, alertas, cobrancas, configuracoes, clientes, manutencao
from src.domain.valores import hoje_br
from src.ui.componentes import (
    barra_segmentada,
    cabecalho,
    cabecalho_pagina,
    cartao_html,
    estado_vazio,
    item_alerta,
    kpi,
    kpi_grade,
    botao_acao,
    legenda_ocupacao,
    paineis,
    proteger,
    selo_situacao,
)
from src.ui.registros import campo, lista_registros, registro
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
_STATUS_FROTA = (
    ("alugada", "alugadas"),
    ("disponivel", "disponíveis"),
    ("manutencao", "manutenção"),
    ("inativa", "inativas"),
)


def _data_por_extenso(data):
    return f"{_DIAS[data.weekday()]}, {data.day} de {_MESES[data.month - 1]} de {data.year}"


def _cabecalho_pagina():
    cabecalho_pagina(
        "Dashboard",
        sub=_data_por_extenso(hoje_br()),
        sobretitulo="Visão geral da operação",
        lateral='<div class="painel-status">Cobranças atualizadas nesta consulta</div>',
    )


def _faixa_instrumentos(dados, contagem, devedores_count, ordens_concluidas):
    frota_total = len(dados["frota"])
    ativas = sum(1 for m in dados["frota"] if m["status"] != "inativa")
    alugadas = contagem.get("alugada", 0)
    ocupacao = round(100 * alugadas / ativas) if ativas else 0
    total_base = max(frota_total, 1)
    previsto = dados["previsto"]
    recebido = dados["recebido"]
    progresso_recebido = (
        min(100, round(100 * recebido / previsto)) if previsto else 0
    )

    segmentos = barra_segmentada(
        [(round(100 * contagem.get(chave, 0) / total_base, 1), chave) for chave, _ in _STATUS_FROTA]
    )
    legenda = legenda_ocupacao(
        [(f"{contagem.get(chave, 0)} {rotulo}", chave) for chave, rotulo in _STATUS_FROTA]
    )
    barra_recebido = barra_segmentada([(progresso_recebido, "disponivel")])

    kpi_grade(
        [
            kpi(
                "frota",
                frota_total,
                contexto=f"motos · {ocupacao}% ocupação",
                extra=segmentos + legenda,
            ),
            kpi(
                "recebido no mês",
                formatar_moeda_compacta(recebido),
                contexto=f"de {formatar_moeda_compacta(previsto)} previstos",
                extra=barra_recebido,
            ),
            kpi(
                "em atraso",
                formatar_moeda_compacta(dados["atrasado"]),
                contexto=f"{devedores_count} cliente(s) atrasado(s)",
                tom="perigo" if dados["atrasado"] else None,
            ),
            kpi(
                "manutenção no mês",
                formatar_moeda_compacta(dados["manutencao"]),
                contexto=f"{ordens_concluidas} ordem(ns) concluída(s)",
            ),
        ]
    )


def _situacao_cobranca_html(cobranca):
    if cobranca["situacao"] == "atrasada":
        dias = max((hoje_br() - _iso_data(cobranca["vencimento"])).days, 0)
        return selo_situacao(f"Atraso {dias}d", "atrasada")
    return selo_situacao("Vence hoje", "proxima")


def _iso_data(valor):
    from datetime import date

    return date.fromisoformat(str(valor)[:10])


def _cartao_hoje(cobrancas_hoje, placas, nomes):
    with lista_registros("dashboard_hoje", acoes=1):
        st.markdown(
            """
            <div class="cartao__cab">
              <h2 class="cartao__titulo">Hoje</h2>
              <span class="cartao__meta">vencendo hoje e atrasadas</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not cobrancas_hoje:
            st.markdown(
                estado_vazio("Nenhuma cobrança vencendo hoje ou atrasada.", compacto=True),
                unsafe_allow_html=True,
            )
        for c in cobrancas_hoje:
            nome = nomes.get(c["cliente_id"], "—")
            campos = [
                campo("Moto", f'<span class="mono fs-secundario texto-2">{escape(placas.get(c["moto_id"], "—"))}</span>'),
                campo("Vencimento", f'<span class="mono fs-secundario">{formatar_data(c["vencimento"])}</span>'),
                campo("Valor", f'<span class="mono fs-secundario">{formatar_moeda(c["valor"])}</span>'),
            ]
            with registro(
                "dashboard_hoje",
                c["id"],
                f'<span class="fs-secundario">{escape(nome)}</span>',
                campos,
                selo=_situacao_cobranca_html(c),
            ) as acoes:
                if botao_acao(
                    acoes,
                    "pagar",
                    f"pagar_hoje_{c['id']}",
                    ajuda=f"Registrar o pagamento de {nome if nome != '—' else 'cliente'}",
                ):
                    st.session_state["cobranca_rapida"] = c["id"]
                    st.switch_page("pages/5_Cobrancas.py")


def _cartao_alertas(dados_config, alertas_manutencao, alertas_documentos, alertas_cnh):
    itens = []

    vencidas = [a for a in alertas_manutencao if a["situacao"] == "vencida"]
    if vencidas:
        nomes = ", ".join(dict.fromkeys(a["item"] for a in vencidas[:2]))
        if len(vencidas) > 2:
            nomes += f" e mais {len(vencidas) - 2}"
        itens.append(item_alerta(len(vencidas), "Manutenção vencida", nomes, "perigo"))

    proximas = [a for a in alertas_manutencao if a["situacao"] == "proxima"]
    if proximas:
        descricao = (
            f"nos próximos {dados_config['alerta_manutencao_km']} km ou "
            f"{dados_config['alerta_manutencao_dias']} dias"
        )
        itens.append(item_alerta(len(proximas), "Manutenção próxima", descricao, "alerta"))

    doc_vencidos = [a for a in alertas_documentos if a["situacao"] == "vencido"]
    if doc_vencidos:
        primeiro = doc_vencidos[0]
        descricao = f"{primeiro['tipo'].upper()} · moto {primeiro['placa']}"
        if len(doc_vencidos) > 1:
            descricao += f" e mais {len(doc_vencidos) - 1}"
        itens.append(item_alerta(len(doc_vencidos), "Documento vencido", descricao, "perigo"))

    doc_a_vencer = [a for a in alertas_documentos if a["situacao"] == "a_vencer"]
    if doc_a_vencer:
        descricao = f"próximos {dados_config['alerta_documento_dias']} dias"
        itens.append(item_alerta(len(doc_a_vencer), "Documento a vencer", descricao, "alerta"))

    cnh_vencidas = [a for a in alertas_cnh if a["situacao"] == "vencida"]
    if cnh_vencidas:
        primeiro = cnh_vencidas[0]
        descricao = f"{primeiro['nome']} · {formatar_data(primeiro['cnh_validade'])}"
        if len(cnh_vencidas) > 1:
            descricao += f" e mais {len(cnh_vencidas) - 1}"
        itens.append(item_alerta(len(cnh_vencidas), "CNH vencida", descricao, "perigo"))

    cnh_a_vencer = [a for a in alertas_cnh if a["situacao"] == "a_vencer"]
    if cnh_a_vencer:
        primeiro = cnh_a_vencer[0]
        descricao = f"{primeiro['nome']} · {formatar_data(primeiro['cnh_validade'])}"
        if len(cnh_a_vencer) > 1:
            descricao += f" e mais {len(cnh_a_vencer) - 1}"
        itens.append(item_alerta(len(cnh_a_vencer), "CNH a vencer", descricao, "alerta"))

    corpo = (
        '<div class="alerta-lista">' + "".join(itens) + "</div>"
        if itens
        else estado_vazio("Nenhum alerta no momento.", compacto=True)
    )
    st.markdown(cartao_html("Alertas", corpo), unsafe_allow_html=True)


def exibir():
    cabecalho("Dashboard", exibir_titulo=False)
    with proteger(nova_tentativa=True):
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
        _faixa_instrumentos(dados, contagem, len(dados["devedores"]), ordens_concluidas)
        st.write("")
        # Hoje e Alertas lado a lado só enquanto cada um tem largura útil; senão Alertas vai para baixo de Hoje
        with paineis("dashboard") as (painel_hoje, painel_alertas):
            with painel_hoje:
                _cartao_hoje(cobrancas_hoje, placas, nomes)
            with painel_alertas:
                _cartao_alertas(
                    configuracoes.obter(),
                    alertas.listar_manutencao(),
                    alertas.listar_documentos(),
                    alertas.listar_cnh(),
                )
