"""Contratos: lista, assistente de novo contrato e ficha — segue Contratos.dc.html,
ContratoNovo.dc.html e ContratoFicha.dc.html do mockup."""

from datetime import date, timedelta

import streamlit as st

from src.services import contratos, motos, clientes, cobrancas, vistorias, manutencao
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import (
    cabecalho,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    tabela_html,
    abrir_ficha_cliente,
)
from src.ui.formatadores import formatar_data, formatar_moeda, mascarar_cpf
from src.ui.vistorias import campos as campos_vistoria, preparar as preparar_vistoria

_STATUS_ROTULO = {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}
_FILTROS = ["Todos", "ativo", "encerrado", "cancelado"]
_PERIODOS = ["diario", "semanal", "quinzenal", "mensal"]
_PERIODOS_ROTULO = {"diario": "Diário", "semanal": "Semanal", "quinzenal": "Quinzenal", "mensal": "Mensal"}
_ETAPAS_WIZARD = ["Cliente", "Moto", "Condições", "Confirmar"]


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _ir_para_lista():
    for chave in (
        "contratos_visao",
        "contratos_id_selecionado",
        "contrato_etapa",
        "contrato_cliente_id",
        "contrato_moto_id",
        "contrato_condicoes",
    ):
        st.session_state.pop(chave, None)
    st.rerun()


def _ir_para_ficha(contrato_id):
    st.session_state["contratos_visao"] = "ficha"
    st.session_state["contratos_id_selecionado"] = contrato_id
    st.rerun()


def _iniciar_wizard():
    st.session_state["contratos_visao"] = "wizard"
    st.session_state["contrato_etapa"] = 1
    st.rerun()


def _iniciais(nome):
    return (nome or "?").strip()[:1].upper()


# ------------------------------------------------------------------ lista --

def _exibir_lista():
    registros = contratos.listar()
    contagem = {
        chave: sum(1 for c in registros if c["status"] == chave)
        for chave in ("ativo", "encerrado", "cancelado")
    }
    frota = {m["id"]: m for m in motos.listar()}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}

    col_titulo, col_botao = st.columns([5, 1], vertical_alignment="center")
    col_titulo.markdown(
        f"""
        <h1 class="rotulo pagina-titulo">Contratos</h1>
        <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">{contagem.get('ativo', 0)} contrato(s) ativo(s)</div>
        """,
        unsafe_allow_html=True,
    )
    with col_botao:
        if st.button("+ Novo contrato", type="primary", use_container_width=True):
            _iniciar_wizard()

    st.write("")
    filtro_atual = st.session_state.get("contratos_filtro", "ativo")
    col_pills, col_busca = st.columns([3, 1.3])
    with col_pills:
        with st.container(key="contratos_filtros"):
            pills = st.columns(len(_FILTROS))
            rotulos_pill = ["Todos"] + [_STATUS_ROTULO[f] for f in _FILTROS[1:]]
            for coluna, valor, rotulo in zip(pills, _FILTROS, rotulos_pill):
                total_pill = len(registros) if valor == "Todos" else contagem.get(valor, 0)
                if coluna.button(
                    f"{rotulo} · {total_pill}",
                    key=f"pill_ct_{valor}",
                    type="primary" if filtro_atual == valor else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["contratos_filtro"] = valor
                    st.rerun()
    with col_busca:
        busca = st.text_input(
            "Buscar", placeholder="Buscar por cliente ou placa", label_visibility="collapsed"
        )

    busca_normalizada = busca.casefold()
    filtrados = [
        c
        for c in registros
        if (filtro_atual == "Todos" or c["status"] == filtro_atual)
        and (
            busca_normalizada in nomes.get(c["cliente_id"], "").casefold()
            or busca_normalizada in frota.get(c["moto_id"], {}).get("placa", "").casefold()
        )
    ]
    filtrados.sort(key=lambda c: c["data_inicio"], reverse=True)

    st.write("")
    pagina_chave = "contratos_pagina"
    por_pagina = 7
    total_paginas = max(1, -(-len(filtrados) // por_pagina))
    pagina = min(st.session_state.get(pagina_chave, 1), total_paginas)
    inicio = (pagina - 1) * por_pagina
    pagina_atual = filtrados[inicio : inicio + por_pagina]

    with st.container(key="contratos_card_lista"):
        cab = st.columns([1.5, 1.2, 1.1, 1.2, 1.1, 1.1, 0.4], vertical_alignment="center")
        for coluna, rotulo in zip(
            cab, ["Cliente", "Moto", "Início", "Periodicidade", "Valor / período", "Status", ""]
        ):
            coluna.markdown(f'<span class="fs-secundario texto-2">{rotulo}</span>', unsafe_allow_html=True)
        if not pagina_atual:
            st.markdown(
                '<div class="vazio vazio--linha">Nenhum contrato encontrado.</div>',
                unsafe_allow_html=True,
            )
        for contrato in pagina_atual:
            moto = frota.get(contrato["moto_id"])
            muted = "color:var(--texto-3);" if contrato["status"] != "ativo" else ""
            linha = st.columns([1.5, 1.2, 1.1, 1.2, 1.1, 1.1, 0.4], vertical_alignment="center")
            linha[0].markdown(f'<span style="font-size:var(--fs-secundario);{muted}">{nomes.get(contrato["cliente_id"], "—")}</span>', unsafe_allow_html=True)
            linha[1].markdown(chip_placa(moto["placa"]) if moto else "—", unsafe_allow_html=True)
            linha[2].markdown(f'<span class="mono" style="font-size:var(--fs-secundario);{muted}">{formatar_data(contrato["data_inicio"])}</span>', unsafe_allow_html=True)
            linha[3].markdown(f'<span style="font-size:var(--fs-secundario);{muted or "color:var(--texto-2);"}">{_PERIODOS_ROTULO.get(contrato["periodicidade"], contrato["periodicidade"])}</span>', unsafe_allow_html=True)
            linha[4].markdown(f'<span class="mono" style="font-size:var(--fs-secundario);{muted}">{formatar_moeda(contrato["valor_periodo"])}</span>', unsafe_allow_html=True)
            linha[5].markdown(
                selo_situacao(_STATUS_ROTULO[contrato["status"]], contrato["status"]),
                unsafe_allow_html=True,
            )
            if linha[6].button("→", key=f"ficha_ct_{contrato['id']}", help="Ver contrato"):
                _ir_para_ficha(contrato["id"])

    if total_paginas > 1:
        st.caption(f"Mostrando {len(pagina_atual)} de {len(filtrados)} · página {pagina} de {total_paginas}")
        col_ant, col_prox = st.columns(2)
        if col_ant.button("‹ Anterior", disabled=pagina <= 1, key="ct_ant"):
            st.session_state[pagina_chave] = pagina - 1
            st.rerun()
        if col_prox.button("Próxima ›", disabled=pagina >= total_paginas, key="ct_prox"):
            st.session_state[pagina_chave] = pagina + 1
            st.rerun()


# ----------------------------------------------------------------- wizard --

def _indicador_etapas_contrato(atual):
    itens = ""
    for i, rotulo in enumerate(_ETAPAS_WIZARD, start=1):
        concluido = i < atual
        corrente = i == atual
        if concluido or corrente:
            cor_fundo, cor_borda, cor_texto = "var(--chip-fundo)", "var(--chip-fundo)", "var(--chip-texto)"
        else:
            cor_fundo, cor_borda, cor_texto = "transparent", "var(--linha)", "var(--texto-3)"
        anel = "box-shadow:0 0 0 3px var(--linha-forte);" if corrente else ""
        rotulo_cor = "var(--texto)" if corrente else ("var(--texto-2)" if concluido else "var(--texto-3)")
        rotulo_peso = "600" if corrente else "500"
        if i > 1:
            cor_linha = "var(--texto)" if i <= atual else "var(--linha)"
            itens += f'<div style="flex-grow:1;height:1px;background:{cor_linha};margin:14px 12px 0;"></div>'
        itens += f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;width:120px;">
          <div style="width:28px;height:28px;border-radius:50%;background:{cor_fundo};border:1px solid {cor_borda};
                      {anel}display:flex;align-items:center;justify-content:center;color:{cor_texto};
                      font-size:var(--fs-legenda);font-weight:600;flex-shrink:0;">{i}</div>
          <span style="font-size:var(--fs-secundario);color:{rotulo_cor};font-weight:{rotulo_peso};">{rotulo}</span>
        </div>
        """
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;padding:20px 40px;">{itens}</div>',
        unsafe_allow_html=True,
    )


def _avatar_circulo(texto, cor="var(--chip-fundo)"):
    return (
        f'<div style="width:30px;height:30px;border-radius:50%;background:{cor};color:var(--chip-texto);'
        f'display:flex;align-items:center;justify-content:center;font-size:var(--fs-legenda);font-weight:600;'
        f'flex-shrink:0;">{texto}</div>'
    )


def _cartao_selecionavel(chave, icone_html, titulo, subtitulo, badge_html, selecionado, elegivel):
    borda = "2px solid var(--texto)" if selecionado else "1px solid var(--linha)"
    fundo = "var(--superficie-hover)" if selecionado else "var(--superficie)"
    opacidade = "1" if elegivel else "0.55"
    st.markdown(
        f"""
        <style>.st-key-{chave} {{
          border:{borda} !important; background:{fundo} !important; border-radius:var(--raio-lg);
          padding:14px 16px; opacity:{opacidade}; margin-bottom:10px;
        }}</style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key=chave):
        col_info, col_badge, col_sel = st.columns([3, 1.6, 0.5], vertical_alignment="center")
        col_info.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;">
              {icone_html}
              <div>
                <div style="font-size:var(--fs-secundario);font-weight:500;">{titulo}</div>
                <div class="mono" style="font-size:var(--fs-legenda);color:var(--texto-2);">{subtitulo}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_badge.markdown(badge_html, unsafe_allow_html=True)
        rotulo_botao = "✓" if selecionado else "selecionar"
        return col_sel.button(rotulo_botao, key=f"sel_{chave}", disabled=not elegivel)


def _wizard_etapa1():
    pessoas = clientes.listar()
    contratos_ativos = {c["cliente_id"]: c["moto_id"] for c in contratos.listar() if c["status"] == "ativo"}
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    busca = st.text_input(
        "Buscar", placeholder="Buscar cliente por nome ou CPF", label_visibility="collapsed", key="wizard_busca_cliente"
    )
    busca_normalizada = busca.casefold()
    candidatos = [
        c
        for c in pessoas
        if busca_normalizada in c["nome"].casefold() or busca_normalizada in (c.get("cpf") or "")
    ]
    selecionado_id = st.session_state.get("contrato_cliente_id")
    for cliente in candidatos:
        elegivel = cliente["status"] == "ativo"
        moto_atual = contratos_ativos.get(cliente["id"])
        if not elegivel:
            badge = f'<span style="font-size:var(--fs-legenda);color:var(--perigo-texto);">{"bloqueado" if cliente["status"] == "bloqueado" else "inativo"} · não pode alugar</span>'
        elif moto_atual:
            badge = f'<span style="font-size:var(--fs-legenda);color:var(--texto-2);">já aluga {placas.get(moto_atual, "—")}</span>'
        else:
            badge = ""
        avatar_cor = "var(--chip-fundo)" if elegivel else "var(--avatar-inativo)"
        if _cartao_selecionavel(
            f"cli_card_{cliente['id']}",
            _avatar_circulo(_iniciais(cliente["nome"]), avatar_cor),
            cliente["nome"],
            mascarar_cpf(cliente.get("cpf") or ""),
            badge,
            selecionado_id == cliente["id"],
            elegivel,
        ):
            st.session_state["contrato_cliente_id"] = cliente["id"]
            st.rerun()
    if not candidatos:
        st.info("Nenhum cliente encontrado.")


def _wizard_etapa2():
    frota = [m for m in motos.listar() if m["status"] == "disponivel"]
    busca = st.text_input(
        "Buscar", placeholder="Buscar moto disponível por placa ou modelo",
        label_visibility="collapsed", key="wizard_busca_moto",
    )
    busca_normalizada = busca.casefold()
    candidatos = [
        m for m in frota
        if busca_normalizada in m["placa"].casefold() or busca_normalizada in f"{m['marca']} {m['modelo']}".casefold()
    ]
    selecionado_id = st.session_state.get("contrato_moto_id")
    for moto in candidatos:
        km_fmt = f"{moto['km_atual']:,}".replace(",", ".")
        sugerida = formatar_moeda(moto.get("valor_locacao_sugerido")) if moto.get("valor_locacao_sugerido") else "—"
        subtitulo = f"{km_fmt} km · sugerida {sugerida}/mês"
        if _cartao_selecionavel(
            f"moto_card_{moto['id']}",
            chip_placa(moto["placa"]),
            f"{moto['marca']} {moto['modelo']}",
            subtitulo,
            "",
            selecionado_id == moto["id"],
            True,
        ):
            st.session_state["contrato_moto_id"] = moto["id"]
            st.rerun()
    if not candidatos:
        st.info("Nenhuma moto disponível encontrada.")


def _wizard_etapa3():
    moto = next(m for m in motos.listar() if m["id"] == st.session_state["contrato_moto_id"])
    condicoes_atuais = st.session_state.get("contrato_condicoes", {})

    col_data, col_periodo = st.columns([1, 2.5])
    with col_data:
        inicio = campo_data("Data de início", condicoes_atuais.get("data_inicio") or hoje_br().isoformat())
    with col_periodo:
        st.markdown('<span style="font-size:var(--fs-legenda);color:var(--texto-2);">Periodicidade</span>', unsafe_allow_html=True)
        periodicidade_atual = st.session_state.get("wizard_periodicidade", "mensal")
        with st.container(key="contrato_periodicidade"):
            cols = st.columns(len(_PERIODOS))
            for coluna, valor in zip(cols, _PERIODOS):
                if coluna.button(
                    _PERIODOS_ROTULO[valor],
                    key=f"periodo_{valor}",
                    type="primary" if periodicidade_atual == valor else "secondary",
                ):
                    st.session_state["wizard_periodicidade"] = valor
                    st.rerun()

    col_valor, col_caucao = st.columns(2)
    valor = col_valor.text_input(
        "Valor do período (R$)",
        condicoes_atuais.get("valor_periodo") or str(moto.get("valor_locacao_sugerido") or "0"),
    )
    caucao = col_caucao.text_input("Caução (R$)", condicoes_atuais.get("caucao_valor") or "0")

    col_fim, col_km = st.columns(2)
    fim_padrao = (
        date.fromisoformat(condicoes_atuais["data_fim_prevista"])
        if condicoes_atuais.get("data_fim_prevista")
        else hoje_br() + timedelta(days=30)
    )
    fim = col_fim.date_input("Fim previsto", value=fim_padrao, format="DD/MM/YYYY")
    col_km.text_input("Km inicial", f"{moto['km_atual']:,}".replace(",", "."), disabled=True)
    st.caption("Prazo definido é obrigatório nesta versão do assistente.")

    col_voltar, col_avancar = st.columns(2)
    if col_voltar.button("Voltar", key="voltar_3"):
        st.session_state["contrato_etapa"] = 2
        st.rerun()
    if col_avancar.button("Avançar", type="primary", key="avancar_3"):
        try:
            valor_dec = decimal_br(valor, positivo=True)
            caucao_dec = decimal_br(caucao)
        except ValueError as erro:
            st.error(str(erro))
            return
        st.session_state["contrato_condicoes"] = {
            "data_inicio": inicio.isoformat(),
            "data_fim_prevista": fim.isoformat(),
            "periodicidade": periodicidade_atual,
            "valor_periodo": str(valor_dec),
            "caucao_valor": str(caucao_dec),
        }
        st.session_state["contrato_etapa"] = 4
        st.rerun()


def _wizard_etapa4():
    moto = next(m for m in motos.listar() if m["id"] == st.session_state["contrato_moto_id"])
    cliente = next(c for c in clientes.listar() if c["id"] == st.session_state["contrato_cliente_id"])
    condicoes = st.session_state["contrato_condicoes"]

    agenda = contratos.previa_agenda(
        date.fromisoformat(condicoes["data_inicio"]),
        condicoes["periodicidade"],
        decimal_br(condicoes["valor_periodo"], positivo=True),
        date.fromisoformat(condicoes["data_fim_prevista"]),
    )
    caucao_dec = decimal_br(condicoes["caucao_valor"])

    st.markdown(
        f"""
        <div style="background:var(--chip-fundo);border-radius:var(--raio-sm);padding:20px 24px;color:var(--chip-texto);">
          <div class="rotulo" style="font-size:17px;margin-bottom:12px;">{cliente['nome']} vai alugar {moto['placa']} · {moto['marca']} {moto['modelo']}</div>
          <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;">
            <div style="display:flex;flex-direction:column;gap:2px;"><span style="font-size:var(--fs-legenda);color:var(--texto-3);">periodicidade</span><span style="font-size:var(--fs-secundario);">{_PERIODOS_ROTULO[condicoes['periodicidade']]}</span></div>
            <div style="display:flex;flex-direction:column;gap:2px;"><span style="font-size:var(--fs-legenda);color:var(--texto-3);">valor / período</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(condicoes['valor_periodo'])}</span></div>
            <div style="display:flex;flex-direction:column;gap:2px;"><span style="font-size:var(--fs-legenda);color:var(--texto-3);">início</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(condicoes['data_inicio'])}</span></div>
            <div style="display:flex;flex-direction:column;gap:2px;"><span style="font-size:var(--fs-legenda);color:var(--texto-3);">caução</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(condicoes['caucao_valor'])}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown('<h3 class="rotulo" style="margin:0 0 10px;font-size:14px;">Prévia da agenda de cobranças</h3>', unsafe_allow_html=True)
    linhas = []
    if caucao_dec > 0:
        linhas.append(["Caução", f'<span class="mono">{formatar_data(condicoes["data_inicio"])}</span>', f'<span class="mono">{formatar_moeda(caucao_dec)}</span>'])
    for item in agenda:
        linhas.append(
            [
                f"Parcela {item['numero']}",
                f'<span class="mono">{formatar_data(item["vencimento"].isoformat())}</span>',
                f'<span class="mono">{formatar_moeda(item["valor"])}</span>',
            ]
        )
    tabela_html(["Item", "Vencimento", "Valor"], linhas)

    st.write("")
    st.markdown('<h3 class="rotulo" style="margin:0 0 10px;font-size:14px;">Vistoria de entrega</h3>', unsafe_allow_html=True)
    with st.form("novo_contrato_" + moto["id"]):
        vistoria = campos_vistoria("entrega", moto["km_atual"])
        col_voltar, col_criar = st.columns(2)
        voltar = col_voltar.form_submit_button("Voltar")
        criar = col_criar.form_submit_button("Criar contrato", type="primary")
    if voltar:
        st.session_state["contrato_etapa"] = 3
        st.rerun()
    if criar:
        dados_vistoria = preparar_vistoria(vistoria)
        contratos.criar_com_vistoria(
            {
                "moto_id": moto["id"],
                "cliente_id": cliente["id"],
                "km_inicial": dados_vistoria["km"],
                **condicoes,
            },
            dados_vistoria,
        )
        for chave in (
            "contratos_visao",
            "contrato_etapa",
            "contrato_cliente_id",
            "contrato_moto_id",
            "contrato_condicoes",
            "wizard_periodicidade",
        ):
            st.session_state.pop(chave, None)
        _salvo("Contrato criado. Anexe as fotos da vistoria na página Vistorias.")


def _exibir_wizard():
    if st.button("‹ Contratos", key="voltar_wizard"):
        _ir_para_lista()
    etapa = st.session_state.setdefault("contrato_etapa", 1)

    col_titulo, col_cancelar = st.columns([4, 1], vertical_alignment="center")
    col_titulo.markdown(
        """
        <h1 class="rotulo" style="margin:0;font-size:24px;">Novo contrato</h1>
        <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">assistente em 4 etapas</div>
        """,
        unsafe_allow_html=True,
    )
    with col_cancelar:
        if st.button("Cancelar", use_container_width=True):
            _ir_para_lista()

    _indicador_etapas_contrato(etapa)
    st.write("")

    if etapa == 1:
        _wizard_etapa1()
        if st.button("Avançar", type="primary", disabled=not st.session_state.get("contrato_cliente_id")):
            st.session_state["contrato_etapa"] = 2
            st.rerun()
    elif etapa == 2:
        _wizard_etapa2()
        col_voltar, col_avancar = st.columns(2)
        if col_voltar.button("Voltar", key="voltar_2"):
            st.session_state["contrato_etapa"] = 1
            st.rerun()
        if col_avancar.button("Avançar", type="primary", key="avancar_2", disabled=not st.session_state.get("contrato_moto_id")):
            st.session_state["contrato_etapa"] = 3
            st.rerun()
    elif etapa == 3:
        _wizard_etapa3()
    elif etapa == 4:
        _wizard_etapa4()

    st.caption(f"Etapa {etapa} de 4")


# ------------------------------------------------------------------ ficha --

@st.dialog("Encerrar contrato")
def _dialog_encerrar(contrato, moto, cliente):
    st.markdown(f'{chip_placa(moto["placa"])} <span style="margin-left:8px;">{cliente["nome"]}</span>', unsafe_allow_html=True)
    with st.form("encerrar_" + contrato["id"]):
        data = campo_data("Data de encerramento", hoje_br().isoformat())
        km_final = st.number_input(
            "Km final", min_value=contrato["km_inicial"], value=moto["km_atual"], step=1
        )
        st.caption(f"deve ser maior ou igual ao km inicial ({contrato['km_inicial']:,} km)".replace(",", "."))
        devolvida = st.checkbox("Caução devolvida ao cliente", value=True)
        st.caption(f"Cobranças em aberto com vencimento após {formatar_data((data or hoje_br()).isoformat())} serão canceladas automaticamente.")
        moto_atual = next(m for m in motos.listar() if m["id"] == contrato["moto_id"])
        vistoria = campos_vistoria("devolucao", moto_atual["km_atual"])
        if st.form_submit_button("Confirmar encerramento", type="primary", use_container_width=True):
            contratos.encerrar_com_vistoria(
                contrato["id"], data or hoje_br(), preparar_vistoria(vistoria), devolvida
            )
            _salvo("Contrato encerrado.")


def _cabecalho_ficha(contrato, moto, cliente):
    if contrato["status"] == "ativo" and moto:
        linha = f"Ativo · desde {formatar_data(contrato['data_inicio'])} · {contrato['periodicidade']}"
    else:
        linha = f"{_STATUS_ROTULO[contrato['status']]} · desde {formatar_data(contrato['data_inicio'])}"
    col_titulo, col_acao = st.columns([3, 1], vertical_alignment="center")
    with col_titulo:
        st.markdown(
            f"""
            <h1 class="rotulo" style="margin:0;font-size:22px;">{cliente['nome']} → {moto['marca']} {moto['modelo']}
              {chip_placa(moto['placa'])}
            </h1>
            <div style="font-size:var(--fs-secundario);margin-top:6px;">{selo_situacao(linha, contrato["status"])}</div>
            """,
            unsafe_allow_html=True,
        )
    with col_acao:
        if st.button("Ver cliente →", key="ver_cliente_contrato", use_container_width=True):
            abrir_ficha_cliente(cliente["id"])
        if contrato["status"] == "ativo":
            if st.button("Encerrar contrato", key="abrir_encerrar", use_container_width=True):
                _dialog_encerrar(contrato, moto, cliente)


def _faixa_dados_contrato(contrato):
    proximas = [
        c for c in cobrancas.listar_por_contrato(contrato["id"])
        if c["situacao"] == "aberta" and c["tipo"] == "locacao"
    ]
    proximas.sort(key=lambda c: c["vencimento"])
    proxima = formatar_data(proximas[0]["vencimento"]) if proximas else "—"
    prazo = "Indeterminado" if not contrato.get("data_fim_prevista") else formatar_data(contrato["data_fim_prevista"])
    km_inicial = f"{contrato['km_inicial']:,}".replace(",", ".")
    st.markdown(
        f"""
        <div class="cartao cartao--faixa" style="margin-bottom:24px;">
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">valor / período</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['valor_periodo'])}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">caução</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['caucao_valor'])}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">km inicial</span><span class="mono" style="font-size:var(--fs-secundario);">{km_inicial} km</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">prazo</span><span style="font-size:var(--fs-secundario);">{prazo}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">próxima cobrança</span><span class="mono" style="font-size:var(--fs-secundario);">{proxima}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _aba_cobrancas(contrato):
    registros = sorted(cobrancas.listar_por_contrato(contrato["id"]), key=lambda c: c["vencimento"])
    linhas = []
    for c in registros:
        pagamentos = cobrancas.historico_pagamentos(c["id"])
        pago_em = formatar_data(pagamentos[-1]["data_pagamento"]) if pagamentos else None
        if c["situacao"] == "paga":
            situacao_html = selo_situacao("Paga", "paga")
        elif c["situacao"] == "atrasada":
            situacao_html = selo_situacao("Atrasada", "atrasada")
        elif c["situacao"] == "cancelada":
            situacao_html = selo_situacao("Cancelada", "cancelada")
        else:
            situacao_html = selo_situacao("Aberta", "")
        linhas.append(
            [
                c["tipo"].capitalize(),
                f'<span class="mono">{formatar_data(c["vencimento"])}</span>',
                f'<span class="mono">{pago_em}</span>' if pago_em else '<span style="color:var(--texto-3);">—</span>',
                f'<span class="mono">{formatar_moeda(c["valor"])}</span>',
                situacao_html,
            ]
        )
    tabela_html(["Tipo", "Vencimento", "Pago em", "Valor", "Situação"], linhas)


def _aba_vistorias(contrato):
    registros = {v["tipo"]: v for v in vistorias.listar_por_contrato(contrato["id"])}
    col_entrega, col_devolucao = st.columns(2, gap="medium")
    for coluna, tipo, titulo in [(col_entrega, "entrega", "Entrega"), (col_devolucao, "devolucao", "Devolução")]:
        vistoria = registros.get(tipo)
        with coluna:
            if not vistoria:
                st.markdown(
                    f"""
                    <div style="background:var(--superficie);border:1px dashed var(--linha);border-radius:var(--raio-sm);padding:18px 22px;
                                display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:10px;height:100%;">
                      <h3 class="rotulo" style="margin:0;font-size:14px;color:var(--texto-2);">{titulo}</h3>
                      <div class="fs-secundario texto-2">Ainda não realizada{" — será registrada no encerramento do contrato." if tipo == "devolucao" else "."}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                continue
            checklist = vistoria.get("checklist") or {}
            avarias = ", ".join(
                nome.replace("_", " ") for nome, estado in checklist.items() if estado == "avaria"
            ) or "Nenhuma"
            st.markdown(
                f"""
                <div class="cartao">
                  <h3 class="rotulo" style="margin:0 0 14px;font-size:14px;">{titulo}</h3>
                  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">data</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(vistoria['data'])}</span></div>
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">km</span><span class="mono" style="font-size:var(--fs-secundario);">{f"{vistoria['km']:,}".replace(",", ".")} km</span></div>
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">combustível</span><span style="font-size:var(--fs-secundario);">{(vistoria.get('nivel_combustivel') or '—').capitalize()}</span></div>
                    <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">avarias</span><span style="font-size:var(--fs-secundario);">{avarias}</span></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _aba_manutencoes(contrato):
    registros = [
        m
        for m in manutencao.listar_manutencoes(contrato["moto_id"])
        if contrato["data_inicio"] <= m["data_entrada"] <= (contrato.get("data_encerramento") or hoje_br().isoformat())
    ]
    registros.sort(key=lambda m: m["data_entrada"], reverse=True)
    linhas = [
        [
            f'<span class="mono">{formatar_data(m["data_entrada"])}</span>',
            m["tipo"].capitalize(),
            m["descricao"],
            f'<span class="mono">{f"{m["km"]:,}".replace(",", ".")} km</span>',
            "Sim" if m.get("cobrar_do_cliente") else '<span style="color:var(--texto-2);">Não</span>',
            f'<span class="mono">{formatar_moeda(m["custo_total"])}</span>',
        ]
        for m in registros
    ]
    tabela_html(["Data", "Tipo", "Descrição", "Km", "Cobrada do cliente", "Custo"], linhas)
    st.caption("Mostrando apenas manutenções realizadas durante a vigência deste contrato.")


def _exibir_ficha(contrato_id):
    contrato = next((c for c in contratos.listar() if c["id"] == contrato_id), None)
    if not contrato:
        st.warning("Contrato não encontrado.")
        _ir_para_lista()
        return
    moto = next((m for m in motos.listar() if m["id"] == contrato["moto_id"]), None)
    cliente = next((c for c in clientes.listar() if c["id"] == contrato["cliente_id"]), None)
    if not moto or not cliente:
        st.warning("Dados do contrato incompletos.")
        return

    if st.button("‹ Contratos", key="voltar_contratos"):
        _ir_para_lista()

    _cabecalho_ficha(contrato, moto, cliente)
    st.write("")
    _faixa_dados_contrato(contrato)

    abas = st.tabs(["Cobranças", "Vistorias", "Manutenções"])
    with abas[0]:
        _aba_cobrancas(contrato)
    with abas[1]:
        _aba_vistorias(contrato)
    with abas[2]:
        _aba_manutencoes(contrato)


def exibir():
    cabecalho("Contratos", exibir_titulo=False)
    with proteger():
        visao = st.session_state.get("contratos_visao", "lista")
        if visao == "wizard":
            _exibir_wizard()
        elif visao == "ficha" and st.session_state.get("contratos_id_selecionado"):
            _exibir_ficha(st.session_state["contratos_id_selecionado"])
        else:
            _exibir_lista()
