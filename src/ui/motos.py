"""Motos: lista e ficha — segue Motos.dc.html e MotoFicha.dc.html do mockup."""

from datetime import date

import streamlit as st

from src.services import (
    motos,
    manutencao,
    documentos,
    contratos,
    relatorios,
    clientes,
    cobrancas,
)
from src.domain.valores import hoje_br, decimal_br
from src.ui.componentes import (
    cabecalho,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    tabela_html,
    abrir_ficha_contrato,
)
from src.ui.formatadores import (
    formatar_data,
    formatar_moeda,
    formatar_moeda_compacta,
    formatar_placa,
)

_STATUS_ROTULO = {
    "disponivel": "Disponível",
    "alugada": "Alugada",
    "manutencao": "Manutenção",
    "inativa": "Inativa",
}
_FILTROS = ["Todas", "disponivel", "alugada", "manutencao", "inativa"]


def _salvo(mensagem="Alterações salvas."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _ir_para_ficha(moto_id):
    st.session_state["motos_visao"] = "ficha"
    st.session_state["motos_id_selecionado"] = moto_id
    st.rerun()


def _ir_para_lista():
    st.session_state["motos_visao"] = "lista"
    st.session_state.pop("motos_id_selecionado", None)
    st.rerun()


def _iniciais(nome):
    return (nome or "?").strip()[:1].upper()


# ---------------------------------------------------------------- diálogos --

@st.dialog("Nova moto")
def _dialog_nova_moto():
    _formulario_moto(None)


@st.dialog("Editar dados da moto")
def _dialog_editar_moto(moto):
    _formulario_moto(moto)


def _formulario_moto(moto):
    moto = moto or {}
    with st.form("form_moto_" + moto.get("id", "novo")):
        dados = {}
        for campo, titulo in [
            ("placa", "Placa"),
            ("marca", "Marca"),
            ("modelo", "Modelo"),
            ("renavam", "Renavam"),
            ("chassi", "Chassi"),
            ("cor", "Cor"),
        ]:
            dados[campo] = st.text_input(titulo, value=moto.get(campo) or "")
        col1, col2 = st.columns(2)
        dados["ano_fabricacao"] = col1.number_input(
            "Ano fabricação", min_value=1900, max_value=2100,
            value=moto.get("ano_fabricacao") or 2026,
        )
        dados["ano_modelo"] = col2.number_input(
            "Ano modelo", min_value=1900, max_value=2100,
            value=moto.get("ano_modelo") or 2026,
        )
        if not moto:
            dados["km_atual"] = st.number_input(
                "Quilometragem inicial", min_value=0, step=1
            )
        aquisicao = st.text_input(
            "Valor de aquisição (R$)", str(moto.get("valor_aquisicao") or "0")
        )
        locacao = st.text_input(
            "Locação sugerida (R$)", str(moto.get("valor_locacao_sugerido") or "0")
        )
        data = campo_data("Data de aquisição", moto.get("data_aquisicao"))
        dados["data_aquisicao"] = data.isoformat() if data else None
        dados["observacoes"] = st.text_area("Observações", moto.get("observacoes") or "")
        if st.form_submit_button("Salvar moto", type="primary", use_container_width=True):
            dados.update(
                valor_aquisicao=str(decimal_br(aquisicao)),
                valor_locacao_sugerido=str(decimal_br(locacao)),
            )
            if moto:
                motos.atualizar(moto["id"], dados)
            else:
                motos.criar(dados)
            _salvo()


@st.dialog("Atualizar quilometragem")
def _dialog_km(moto):
    st.markdown(chip_placa(moto["placa"]), unsafe_allow_html=True)
    with st.form("form_km_" + moto["id"]):
        km = st.number_input(
            "Nova leitura", min_value=0, value=moto["km_atual"], step=1
        )
        confirmar = st.checkbox(
            "Confirmo o lançamento de uma leitura histórica menor "
            "(o km atual será mantido)"
        )
        if st.form_submit_button("Registrar leitura", type="primary", use_container_width=True):
            motos.atualizar_km(moto["id"], km, confirmar_km_menor=confirmar)
            _salvo("Quilometragem atualizada.")


@st.dialog("Regularizar documento")
def _dialog_regularizar(documento):
    st.write(f"**{documento['tipo'].upper()}** · vencimento {formatar_data(documento['vencimento'])}")
    with st.form("form_regularizar_" + documento["id"]):
        data = campo_data("Data de regularização", hoje_br().isoformat())
        if st.form_submit_button("Confirmar", type="primary", use_container_width=True):
            documentos.regularizar(documento["id"], data or hoje_br())
            _salvo("Documento regularizado.")


# ------------------------------------------------------------------ lista --

def _exibir_lista():
    registros = motos.listar()
    contagem = {
        chave: sum(1 for m in registros if m["status"] == chave)
        for chave in ("disponivel", "alugada", "manutencao", "inativa")
    }
    contratos_ativos = {c["moto_id"]: c["cliente_id"] for c in contratos.listar() if c["status"] == "ativo"}
    nomes_cliente = {c["id"]: c["nome"] for c in clientes.listar()}

    col_titulo, col_botao = st.columns([5, 1], vertical_alignment="center")
    col_titulo.markdown(
        f"""
        <h1 class="rotulo pagina-titulo">Motos</h1>
        <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">{len(registros)} moto(s) cadastrada(s)</div>
        """,
        unsafe_allow_html=True,
    )
    with col_botao:
        if st.button("+ Nova moto", type="primary", use_container_width=True):
            _dialog_nova_moto()

    st.write("")
    filtro_atual = st.session_state.get("motos_filtro", "Todas")
    col_pills, col_busca = st.columns([3, 1.3])
    with col_pills:
        with st.container(key="motos_filtros"):
            pills = st.columns(len(_FILTROS))
            rotulos_pill = ["Todas"] + [_STATUS_ROTULO[f] for f in _FILTROS[1:]]
            for coluna, valor, rotulo in zip(pills, _FILTROS, rotulos_pill):
                total_pill = len(registros) if valor == "Todas" else contagem.get(valor, 0)
                if coluna.button(
                    f"{rotulo} · {total_pill}",
                    key=f"pill_{valor}",
                    type="primary" if filtro_atual == valor else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["motos_filtro"] = valor
                    st.rerun()
    with col_busca:
        busca = st.text_input(
            "Buscar", placeholder="Buscar por placa ou modelo", label_visibility="collapsed"
        )

    filtradas = [
        m
        for m in registros
        if (filtro_atual == "Todas" or m["status"] == filtro_atual)
        and busca.casefold() in f"{m['placa']} {m['marca']} {m['modelo']}".casefold()
    ]

    st.write("")
    pagina_chave = "motos_pagina"
    por_pagina = 7
    total_paginas = max(1, -(-len(filtradas) // por_pagina))
    pagina = min(st.session_state.get(pagina_chave, 1), total_paginas)
    inicio = (pagina - 1) * por_pagina
    pagina_atual = filtradas[inicio : inicio + por_pagina]

    with st.container(key="motos_card_lista"):
        cab = st.columns([1.3, 1.8, 1.5, 1.4, 1.5, 0.5], vertical_alignment="center")
        for coluna, rotulo in zip(cab, ["Placa", "Modelo", "Km atual", "Status", "Contrato atual", ""]):
            coluna.markdown(
                f'<span class="fs-secundario texto-2">{rotulo}</span>',
                unsafe_allow_html=True,
            )
        if not pagina_atual:
            st.markdown(
                '<div class="vazio vazio--linha">Nenhuma moto encontrada.</div>',
                unsafe_allow_html=True,
            )
        for moto in pagina_atual:
            linha = st.columns([1.3, 1.8, 1.5, 1.4, 1.5, 0.5], vertical_alignment="center")
            linha[0].markdown(chip_placa(moto["placa"]), unsafe_allow_html=True)
            linha[1].markdown(
                f'<span style="font-size:var(--fs-secundario);">{moto["marca"]} {moto["modelo"]}</span>',
                unsafe_allow_html=True,
            )
            sub_km, sub_botao = linha[2].columns([3, 1], vertical_alignment="center")
            sub_km.markdown(
                f'<span class="mono" style="font-size:var(--fs-secundario);">{moto["km_atual"]:,} km</span>'.replace(",", "."),
                unsafe_allow_html=True,
            )
            if sub_botao.button("✎", key=f"km_{moto['id']}", help="Atualizar km"):
                _dialog_km(moto)
            linha[3].markdown(
                selo_situacao(_STATUS_ROTULO[moto["status"]], moto["status"]),
                unsafe_allow_html=True,
            )
            cliente_id = contratos_ativos.get(moto["id"])
            linha[4].markdown(
                f'<span style="font-size:var(--fs-secundario);{"color:var(--texto-3);" if not cliente_id else ""}">'
                f'{nomes_cliente.get(cliente_id, "—") if cliente_id else "—"}</span>',
                unsafe_allow_html=True,
            )
            if linha[5].button("→", key=f"ficha_{moto['id']}", help="Ver ficha"):
                _ir_para_ficha(moto["id"])

    if total_paginas > 1:
        st.caption(f"Mostrando {len(pagina_atual)} de {len(filtradas)} · página {pagina} de {total_paginas}")
        col_ant, col_prox = st.columns(2)
        if col_ant.button("‹ Anterior", disabled=pagina <= 1):
            st.session_state[pagina_chave] = pagina - 1
            st.rerun()
        if col_prox.button("Próxima ›", disabled=pagina >= total_paginas):
            st.session_state[pagina_chave] = pagina + 1
            st.rerun()


# ------------------------------------------------------------------ ficha --

def _card_contrato_ativo(moto_id):
    contrato = next((c for c in contratos.listar() if c["moto_id"] == moto_id and c["status"] == "ativo"), None)
    if not contrato:
        st.markdown(
            """
            <div class="cartao">
              <h3 class="rotulo" style="margin:0 0 6px;font-size:14px;">Contrato ativo</h3>
              <div class="fs-secundario texto-2">Nenhum contrato ativo para esta moto.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    cliente = next((c for c in clientes.listar() if c["id"] == contrato["cliente_id"]), None)
    nome = cliente["nome"] if cliente else "—"
    parcelas = [
        c for c in cobrancas.listar_por_contrato(contrato["id"])
        if c["situacao"] == "aberta" and c["tipo"] == "locacao"
    ]
    parcelas.sort(key=lambda c: c["vencimento"])
    proxima = formatar_data(parcelas[0]["vencimento"]) if parcelas else "—"

    st.markdown(
        f"""
        <div class="cartao">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <h3 class="rotulo" style="margin:0;font-size:14px;">Contrato ativo</h3>
          </div>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
            <div style="width:32px;height:32px;border-radius:50%;background:var(--chip-fundo);color:var(--chip-texto);
                        display:flex;align-items:center;justify-content:center;font-size:var(--fs-secundario);font-weight:600;">{_iniciais(nome)}</div>
            <div>
              <div style="font-size:14px;font-weight:500;">{nome}</div>
              <div style="font-size:var(--fs-legenda);color:var(--texto-2);">desde {formatar_data(contrato['data_inicio'])} · {contrato['periodicidade']}</div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;">
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">valor / período</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['valor_periodo'])}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">próxima cobrança</span><span class="mono" style="font-size:var(--fs-secundario);">{proxima}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">caução</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(contrato['caucao_valor'])}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Ver contratos →", key="ver_contrato"):
        abrir_ficha_contrato(contrato["id"])


def _card_dados_moto(moto):
    st.markdown(
        f"""
        <div class="cartao">
          <h3 class="rotulo" style="margin:0 0 14px;font-size:14px;">Dados da moto</h3>
          <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px 14px;">
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">renavam</span><span class="mono" style="font-size:var(--fs-secundario);">{moto.get('renavam') or '—'}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">chassi</span><span class="mono" style="font-size:var(--fs-secundario);">{moto.get('chassi') or '—'}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">placa</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_placa(moto['placa'])}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">valor de aquisição</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(moto.get('valor_aquisicao'))}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">data de aquisição</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(moto.get('data_aquisicao'))}</span></div>
            <div class="campo"><span style="font-size:var(--fs-legenda);color:var(--texto-2);">status</span><span style="font-size:var(--fs-secundario);">{_STATUS_ROTULO[moto['status']]}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _card_quilometragem(moto_id):
    historico = sorted(motos.historico(moto_id), key=lambda h: h["data"], reverse=True)[:8]
    linhas = "".join(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;
                    {"border-bottom:1px solid var(--linha);" if i < len(historico) - 1 else ""}">
          <span class="mono" style="font-size:var(--fs-secundario);">{f"{h['km']:,}".replace(",", ".")} km</span>
          <span style="font-size:var(--fs-legenda);color:var(--texto-2);">{formatar_data(h['data'])} · {h['origem']}</span>
        </div>
        """
        for i, h in enumerate(historico)
    )
    if not historico:
        linhas = '<div style="padding:8px 0;color:var(--texto-2);font-size:var(--fs-secundario);">Nenhuma leitura registrada.</div>'
    st.markdown(
        f"""
        <div class="cartao" style="height:100%;">
          <h3 class="rotulo" style="margin:0 0 14px;font-size:14px;">Quilometragem</h3>
          {linhas}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _aba_resumo(moto):
    esquerda, direita = st.columns([1.5, 1], gap="medium")
    with esquerda:
        _card_contrato_ativo(moto["id"])
        st.write("")
        _card_dados_moto(moto)
    with direita:
        _card_quilometragem(moto["id"])


def _aba_plano(moto):
    plano = manutencao.listar_plano_moto(moto["id"])
    linhas = []
    for item in plano:
        situacao = manutencao.situacao_item_plano(item, moto["km_atual"])
        intervalo = " / ".join(
            filter(
                None,
                [
                    f"{item['intervalo_km_efetivo']:,} km".replace(",", ".") if item["intervalo_km_efetivo"] else None,
                    f"{item['intervalo_dias_efetivo']} dias" if item["intervalo_dias_efetivo"] else None,
                ],
            )
        )
        if item["proxima_km"] is not None:
            restante = f"{item['proxima_km'] - moto['km_atual']:,} km".replace(",", ".")
        elif item["proxima_data"]:
            dias = (date.fromisoformat(item["proxima_data"]) - hoje_br()).days
            restante = f"{dias} dias"
        else:
            restante = "—"
        linhas.append(
            [
                item["item"]["nome"],
                f'<span style="color:var(--texto-2);">{intervalo or "—"}</span>',
                f'<span class="mono">{f"{item["ultima_km"]:,}".replace(",", ".") + " km" if item["ultima_km"] else "—"}</span>',
                f'<span class="mono">{f"{item["proxima_km"]:,}".replace(",", ".") + " km" if item["proxima_km"] else "—"}</span>',
                f'<span class="mono">{restante}</span>',
                selo_situacao(
                    {"vencida": "Vencida", "proxima": "Próxima", "em_dia": "Em dia"}[situacao],
                    situacao,
                ),
            ]
        )
    tabela_html(["Item", "Intervalo", "Última", "Próxima", "Restante", "Situação"], linhas)


def _aba_historico(moto):
    registros = sorted(
        manutencao.listar_manutencoes(moto["id"]), key=lambda m: m["data_entrada"], reverse=True
    )
    linhas = [
        [
            f'<span class="mono">{formatar_data(m["data_entrada"])}</span>',
            m["tipo"].capitalize(),
            m["descricao"],
            f'<span class="mono">{f"{m["km"]:,}".replace(",", ".")} km</span>',
            m.get("oficina") or "—",
            f'<span class="mono">{formatar_moeda(m["custo_total"])}</span>',
        ]
        for m in registros
    ]
    tabela_html(
        ["Data", "Tipo", "Descrição", "Km", "Oficina", "Custo"],
        linhas,
    )


def _aba_documentos(moto):
    registros = documentos.listar_por_moto(moto["id"])
    with st.container(key="motos_card_documentos"):
        cab = st.columns([1.2, 1.2, 1.2, 1.6, 0.8], vertical_alignment="center")
        for coluna, rotulo in zip(cab, ["Tipo", "Referência", "Vencimento", "Situação", ""]):
            coluna.markdown(f'<span class="fs-secundario texto-2">{rotulo}</span>', unsafe_allow_html=True)
        if not registros:
            st.markdown(
                '<div class="vazio vazio--linha">Nenhum documento cadastrado.</div>',
                unsafe_allow_html=True,
            )
        hoje = hoje_br()
        for doc in registros:
            vencido = not doc["regularizado"] and date.fromisoformat(doc["vencimento"][:10]) < hoje
            situacao = "vencido" if vencido else ("a_vencer" if not doc["regularizado"] else "ok")
            texto_situacao = "Vencido" if vencido else ("A vencer" if not doc["regularizado"] else "Em dia")
            linha = st.columns([1.2, 1.2, 1.2, 1.6, 0.8], vertical_alignment="center")
            linha[0].markdown(f'<span style="font-size:var(--fs-secundario);">{doc["tipo"].upper()}</span>', unsafe_allow_html=True)
            linha[1].markdown(
                f'<span class="fs-secundario texto-2">{doc.get("ano_referencia") or doc.get("descricao") or "—"}</span>',
                unsafe_allow_html=True,
            )
            linha[2].markdown(f'<span class="mono" style="font-size:var(--fs-secundario);">{formatar_data(doc["vencimento"])}</span>', unsafe_allow_html=True)
            linha[3].markdown(selo_situacao(texto_situacao, situacao), unsafe_allow_html=True)
            if not doc["regularizado"]:
                if linha[4].button("Regularizar", key=f"reg_{doc['id']}"):
                    _dialog_regularizar(doc)


def _aba_contratos(moto):
    registros = [c for c in contratos.listar() if c["moto_id"] == moto["id"]]
    registros.sort(key=lambda c: c["data_inicio"], reverse=True)
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    linhas = [
        [
            nomes.get(c["cliente_id"], "—"),
            f'<span class="mono">{formatar_data(c["data_inicio"])}</span>',
            f'<span class="mono">{formatar_data(c["data_encerramento"]) if c["data_encerramento"] else "<span style=color:var(--texto-3)>—</span>"}</span>',
            selo_situacao(
                {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}[c["status"]],
                c["status"],
            ),
            f'<span class="mono">{formatar_moeda(c["valor_periodo"])}</span>',
        ]
        for c in registros
    ]
    tabela_html(["Cliente", "Início", "Fim", "Status", "Valor / período"], linhas)


def _aba_financeiro(moto):
    resultado = relatorios.resultado_por_moto(date(1900, 1, 1), hoje_br())["resultado"]
    dados = next((r for r in resultado if r["moto_id"] == moto["id"]), None)
    if not dados:
        st.info("Sem dados financeiros para esta moto ainda.")
        return
    st.markdown(
        f"""
        <div class="cartao cartao--faixa">
          <div style="flex:1;padding:18px 24px;border-right:1px solid var(--linha);display:flex;flex-direction:column;gap:8px;">
            <span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">receita recebida</span>
            <span class="mono" style="font-size:26px;font-weight:600;color:var(--sucesso-texto);">{formatar_moeda_compacta(dados['receita_recebida'])}</span>
          </div>
          <div style="flex:1;padding:18px 24px;border-right:1px solid var(--linha);display:flex;flex-direction:column;gap:8px;">
            <span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">custo de manutenção</span>
            <span class="mono" style="font-size:26px;font-weight:600;">{formatar_moeda_compacta(dados['custo_manutencao'])}</span>
          </div>
          <div style="flex:1;padding:18px 24px;border-right:1px solid var(--linha);display:flex;flex-direction:column;gap:8px;">
            <span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">custo de documentos</span>
            <span class="mono" style="font-size:26px;font-weight:600;">{formatar_moeda_compacta(dados['custo_documentos'])}</span>
          </div>
          <div style="flex:1;padding:18px 24px;display:flex;flex-direction:column;gap:8px;">
            <span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">resultado</span>
            <span class="mono" style="font-size:26px;font-weight:600;color:{'var(--sucesso-texto)' if dados['resultado'] >= 0 else 'var(--perigo-texto)'};">{formatar_moeda_compacta(dados['resultado'])}</span>
          </div>
        </div>
        <div style="font-size:var(--fs-secundario);color:var(--texto-2);margin-top:16px;">Custo por km rodado desde a aquisição:
          <span class="mono" style="color:var(--texto);font-weight:600;">{formatar_moeda(dados['custo_por_km']) if dados['custo_por_km'] is not None else '—'}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _exibir_ficha(moto_id):
    moto = motos.obter(moto_id)
    if not moto:
        st.warning("Moto não encontrada.")
        _ir_para_lista()
        return

    if st.button("‹ Motos", key="voltar_motos"):
        _ir_para_lista()

    contrato = next((c for c in contratos.listar() if c["moto_id"] == moto_id and c["status"] == "ativo"), None)
    if moto["status"] == "alugada" and contrato:
        cliente = next((c for c in clientes.listar() if c["id"] == contrato["cliente_id"]), None)
        linha_status = f"contrato com {cliente['nome']}" if cliente else "contrato ativo"
    else:
        linha_status = _STATUS_ROTULO[moto["status"]]

    col_cab, col_acoes = st.columns([3, 1], vertical_alignment="center")
    with col_cab:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:16px;">
              {chip_placa(moto['placa'], "grande")}
              <div>
                <h1 class="rotulo" style="margin:0;font-size:24px;">{moto['marca']} {moto['modelo']}</h1>
                <div style="font-size:var(--fs-secundario);margin-top:3px;">
                  {selo_situacao(
                      "Alugada · " + linha_status if moto["status"] == "alugada" else linha_status,
                      moto["status"],
                  )}
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_acoes:
        sub1, sub2 = st.columns(2)
        if sub1.button("Editar", use_container_width=True):
            _dialog_editar_moto(moto)
        if moto["status"] in ("disponivel", "inativa"):
            rotulo_toggle = "Reativar" if moto["status"] == "inativa" else "Inativar"
            if sub2.button(rotulo_toggle, use_container_width=True):
                motos.atualizar(
                    moto["id"],
                    {"status": "disponivel" if moto["status"] == "inativa" else "inativa"},
                )
                _salvo()

    st.write("")
    st.markdown(
        f"""
        <div class="cartao cartao--faixa" style="margin-bottom:20px;">
          <div style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);display:flex;flex-direction:column;gap:4px;">
            <span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">km atual</span>
            <span class="mono" style="font-size:20px;font-weight:600;">{f"{moto['km_atual']:,}".replace(",", ".")} km</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">ano fab. / modelo</span><span class="mono" style="font-size:var(--fs-secundario);">{moto.get('ano_fabricacao') or '—'} / {moto.get('ano_modelo') or '—'}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;border-right:1px solid var(--linha);justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">cor</span><span style="font-size:var(--fs-secundario);">{moto.get('cor') or '—'}</span>
          </div>
          <div class="campo" style="flex:1;padding:14px 22px;justify-content:center;">
            <span style="font-size:var(--fs-legenda);color:var(--texto-2);">locação sugerida</span><span class="mono" style="font-size:var(--fs-secundario);">{formatar_moeda(moto.get('valor_locacao_sugerido'))} / mês</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("✎ Atualizar km", key="km_ficha"):
        _dialog_km(moto)

    abas = st.tabs(
        ["Resumo", "Plano de manutenção", "Histórico", "Documentos", "Contratos", "Financeiro"]
    )
    with abas[0]:
        _aba_resumo(moto)
    with abas[1]:
        _aba_plano(moto)
    with abas[2]:
        _aba_historico(moto)
    with abas[3]:
        _aba_documentos(moto)
    with abas[4]:
        _aba_contratos(moto)
    with abas[5]:
        _aba_financeiro(moto)


def exibir():
    cabecalho("Motos", exibir_titulo=False)
    with proteger():
        visao = st.session_state.get("motos_visao", "lista")
        if visao == "ficha" and st.session_state.get("motos_id_selecionado"):
            _exibir_ficha(st.session_state["motos_id_selecionado"])
        else:
            _exibir_lista()
