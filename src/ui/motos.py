"""Motos: lista e ficha — segue Motos.dc.html e MotoFicha.dc.html do mockup."""

from datetime import date
from html import escape

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
from src.domain import mensagens
from src.domain.entradas import decimal_campo
from src.domain.valores import hoje_br
from src.ui import feedback
from src.ui.componentes import (
    cabecalho,
    cabecalho_pagina,
    vazio_lista,
    proteger,
    campo_data,
    chip_placa,
    selo_situacao,
    tabela_html,
    abrir_ficha_contrato,
    botao_acao,
    botao_voltar,
    cabecalho_ficha,
    cartao_dados,
    cartao_ficha,
    faixa_dados,
    ficha_identidade,
    paineis,
)
from src.ui.formularios import (
    campo_inteiro,
    campo_moeda,
    campo_placa,
    legenda_obrigatorios,
    linha_campos,
    rodape_formulario,
    rotulo_obrigatorio,
)
from src.ui.listas import (
    abas,
    aba_ativa,
    barra_filtros,
    lembrar_registro,
    paginar,
    reiniciar_abas,
    restaurar_posicao,
    rodape_paginacao,
)
from src.ui.registros import campo, lista_registros, registro
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
_OPCOES_FILTRO = [("Todas", "Todas")] + [(chave, _STATUS_ROTULO[chave]) for chave in ("disponivel", "alugada", "manutencao", "inativa")]


def _ir_para_ficha(moto_id):
    reiniciar_abas("motos_ficha_abas")
    lembrar_registro("motos", moto_id)
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
    ano_atual = hoje_br().year
    with st.form("form_moto_" + moto.get("id", "novo")):
        dados = {}
        dados["placa"] = campo_placa("Placa", moto.get("placa"), "moto_placa", obrigatorio=True)
        with linha_campos([1, 1], "moto_marca_modelo") as (col_marca, col_modelo):
            dados["marca"] = col_marca.text_input(rotulo_obrigatorio("Marca"), value=moto.get("marca") or "")
            dados["modelo"] = col_modelo.text_input(rotulo_obrigatorio("Modelo"), value=moto.get("modelo") or "")
        with linha_campos([1, 1], "moto_renavam_chassi") as (col_renavam, col_chassi):
            dados["renavam"] = col_renavam.text_input("Renavam", value=moto.get("renavam") or "")
            dados["chassi"] = col_chassi.text_input("Chassi", value=moto.get("chassi") or "")
        dados["cor"] = st.text_input("Cor", value=moto.get("cor") or "")
        with linha_campos([1, 1], "moto_anos") as (col_fabricacao, col_modelo_ano):
            with col_fabricacao:
                dados["ano_fabricacao"] = campo_inteiro(
                    "Ano de fabricação", moto.get("ano_fabricacao") or ano_atual, "moto_ano_fabricacao",
                    minimo=1900, maximo=2100,
                )
            with col_modelo_ano:
                dados["ano_modelo"] = campo_inteiro(
                    "Ano do modelo", moto.get("ano_modelo") or ano_atual, "moto_ano_modelo",
                    minimo=1900, maximo=2100,
                )
        if not moto:
            dados["km_atual"] = campo_inteiro("Quilometragem inicial", 0, "moto_km", sufixo="km")
        with linha_campos([1, 1], "moto_valores") as (col_aquisicao, col_locacao):
            with col_aquisicao:
                aquisicao = campo_moeda("Valor de aquisição", moto.get("valor_aquisicao"), "moto_aquisicao")
            with col_locacao:
                locacao = campo_moeda(
                    "Locação sugerida",
                    moto.get("valor_locacao_sugerido"),
                    "moto_locacao",
                    ajuda="Valor mensal sugerido ao criar contratos; cada contrato pode usar outro valor.",
                )
        data = campo_data("Data de aquisição", moto.get("data_aquisicao"))
        dados["data_aquisicao"] = data.isoformat() if data else None
        dados["observacoes"] = st.text_area("Observações", moto.get("observacoes") or "")
        legenda_obrigatorios()
        acao = rodape_formulario("Salvar moto", "moto", formulario=True)
        if acao.cancelou:
            st.rerun()
        if acao.confirmou:
            with proteger():
                dados.update(
                    valor_aquisicao=str(decimal_campo(aquisicao, "Valor de aquisição")),
                    valor_locacao_sugerido=str(decimal_campo(locacao, "Locação sugerida")),
                )
                if moto:
                    motos.atualizar(moto["id"], dados)
                else:
                    motos.criar(dados)
                feedback.concluir(mensagens.moto_salva(formatar_placa(dados["placa"]), nova=not moto))


@st.dialog("Atualizar quilometragem")
def _dialog_km(moto):
    st.markdown(chip_placa(moto["placa"]), unsafe_allow_html=True)
    with st.form("form_km_" + moto["id"]):
        km = campo_inteiro("Nova leitura", moto["km_atual"], "moto_nova_leitura", sufixo="km")
        confirmar = st.checkbox(
            "Confirmo o lançamento de uma leitura histórica menor "
            "(o km atual será mantido)"
        )
        acao = rodape_formulario("Registrar leitura", "kmmoto", formulario=True)
        if acao.cancelou:
            st.rerun()
        if acao.confirmou:
            with proteger():
                chave = feedback.chave_operacao("kmmoto", [moto["id"], km, confirmar])
                motos.atualizar_km(moto["id"], km, confirmar_km_menor=confirmar, chave_operacao=chave)
                feedback.concluir(mensagens.km_atualizado(formatar_placa(moto["placa"]), km), "kmmoto")


@st.dialog("Regularizar documento")
def _dialog_regularizar(documento):
    st.write(f"**{documento['tipo'].upper()}** · vencimento {formatar_data(documento['vencimento'])}")
    with st.form("form_regularizar_" + documento["id"]):
        data = campo_data("Data de regularização", hoje_br().isoformat())
        acao = rodape_formulario("Confirmar regularização", "regmoto", formulario=True)
        if acao.cancelou:
            st.rerun()
        if acao.confirmou:
            with proteger():
                documentos.regularizar(documento["id"], data or hoje_br())
                descricao = f"{documento['tipo'].upper()} {documento.get('ano_referencia') or ''}".strip()
                feedback.concluir(mensagens.documento_regularizado(descricao))


# ------------------------------------------------------------------ lista --

def _exibir_lista():
    registros = motos.listar()
    contagem = {
        chave: sum(1 for m in registros if m["status"] == chave)
        for chave in ("disponivel", "alugada", "manutencao", "inativa")
    }
    contratos_ativos = {c["moto_id"]: c["cliente_id"] for c in contratos.listar() if c["status"] == "ativo"}
    nomes_cliente = {c["id"]: c["nome"] for c in clientes.listar()}

    if cabecalho_pagina(
        "Motos",
        sub=f"{len(registros)} moto(s) cadastrada(s)",
        acao={"rotulo": "Nova moto", "chave": "motos_nova"},
    ):
        _dialog_nova_moto()

    filtros = barra_filtros(
        "motos",
        _OPCOES_FILTRO,
        padrao="Todas",
        contagens={"Todas": len(registros), **contagem},
        busca="Buscar por placa ou modelo",
    )
    filtradas = [
        m
        for m in registros
        if (filtros.valor == "Todas" or m["status"] == filtros.valor)
        and filtros.busca.casefold() in f"{m['placa']} {m['marca']} {m['modelo']}".casefold()
    ]
    filtros.resumo(len(filtradas), ("moto", "motos"))
    pagina_atual, pagina = paginar("motos", filtradas)

    with lista_registros("motos", acoes=2):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhuma moto encontrada.", "Ainda não há motos cadastradas.", bool(registros), "Nova moto"),
                unsafe_allow_html=True,
            )
        for moto in pagina_atual:
            cliente_id = contratos_ativos.get(moto["id"])
            sem_contrato = "texto-3" if not cliente_id else ""
            modelo = f"{moto['marca']} {moto['modelo']}"
            campos = [
                campo("Modelo", f'<span class="fs-secundario">{escape(modelo)}</span>'),
                campo("Km atual", f'<span class="mono fs-secundario">{moto["km_atual"]:,} km</span>'.replace(",", ".")),
                campo(
                    "Contrato atual",
                    f'<span class="fs-secundario {sem_contrato}">{escape(nomes_cliente.get(cliente_id, "—")) if cliente_id else "—"}</span>',
                ),
            ]
            with registro(
                "motos",
                moto["id"],
                chip_placa(moto["placa"]),
                campos,
                selo=selo_situacao(_STATUS_ROTULO[moto["status"]], moto["status"]),
            ) as acoes:
                if botao_acao(acoes, "km", f"km_{moto['id']}", ajuda=f"Atualizar o km da moto {formatar_placa(moto['placa'])}"):
                    _dialog_km(moto)
                if botao_acao(acoes, "abrir", f"ficha_{moto['id']}", ajuda=f"Abrir a ficha da moto {formatar_placa(moto['placa'])}"):
                    _ir_para_ficha(moto["id"])

    rodape_paginacao("motos", pagina)
    restaurar_posicao("motos")


# ------------------------------------------------------------------ ficha --

def _card_contrato_ativo(moto_id):
    contrato = next((c for c in contratos.listar() if c["moto_id"] == moto_id and c["status"] == "ativo"), None)
    if not contrato:
        st.markdown(
            cartao_dados("Contrato ativo", '<div class="fs-secundario texto-2">Nenhum contrato ativo para esta moto.</div>'),
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

    acao = {"rotulo": "Ver contrato", "chave": "ver_contrato_moto", "ajuda": f"Abrir o contrato de {nome}"}
    with cartao_ficha("moto_contrato", "Contrato ativo", acao) as ver_contrato:
        if ver_contrato:
            abrir_ficha_contrato(contrato["id"])
        st.markdown(
            f"""
            <div class="resumo-contrato">
              <div class="avatar avatar--grande">{escape(_iniciais(nome))}</div>
              <div class="resumo-contrato__texto">
                <div class="resumo-contrato__titulo">{escape(nome)}</div>
                <div class="fs-legenda texto-2">desde {formatar_data(contrato['data_inicio'])} · {escape(str(contrato['periodicidade']))}</div>
              </div>
            </div>
            <div class="grade-dados grade-dados--compacta">
              <div class="campo"><span class="fs-legenda texto-2">valor / período</span><span class="mono fs-secundario">{formatar_moeda(contrato['valor_periodo'])}</span></div>
              <div class="campo"><span class="fs-legenda texto-2">próxima cobrança</span><span class="mono fs-secundario">{proxima}</span></div>
              <div class="campo"><span class="fs-legenda texto-2">caução</span><span class="mono fs-secundario">{formatar_moeda(contrato['caucao_valor'])}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _card_dados_moto(moto):
    corpo = f"""
      <div class="grade-dados grade-dados--compacta">
        <div class="campo"><span class="fs-legenda texto-2">renavam</span><span class="mono fs-secundario">{escape(str(moto.get('renavam') or '—'))}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">chassi</span><span class="mono fs-secundario">{escape(str(moto.get('chassi') or '—'))}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">placa</span><span class="mono fs-secundario">{formatar_placa(moto['placa'])}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">valor de aquisição</span><span class="mono fs-secundario">{formatar_moeda(moto.get('valor_aquisicao'))}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">data de aquisição</span><span class="mono fs-secundario">{formatar_data(moto.get('data_aquisicao'))}</span></div>
        <div class="campo"><span class="fs-legenda texto-2">status</span><span class="fs-secundario">{_STATUS_ROTULO[moto['status']]}</span></div>
      </div>
    """
    st.markdown(cartao_dados("Dados da moto", corpo), unsafe_allow_html=True)


def _card_quilometragem(moto_id):
    historico = sorted(motos.historico(moto_id), key=lambda h: h["data"], reverse=True)[:8]
    linhas = "".join(
        f"""
        <div class="leitura-km">
          <span class="mono fs-secundario">{f"{h['km']:,}".replace(",", ".")} km</span>
          <span class="fs-legenda texto-2">{formatar_data(h['data'])} · {escape(str(h['origem']))}</span>
        </div>
        """
        for i, h in enumerate(historico)
    )
    if not historico:
        linhas = '<div class="leitura-km leitura-km--vazia">Nenhuma leitura registrada.</div>'
    st.markdown(cartao_dados("Quilometragem", linhas), unsafe_allow_html=True)


def _aba_resumo(moto):
    with paineis("moto_resumo") as (principal, lateral):
        with principal:
            _card_contrato_ativo(moto["id"])
        with lateral:
            _card_quilometragem(moto["id"])
    _card_dados_moto(moto)


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
                f'<span class="texto-2">{intervalo or "—"}</span>',
                f'<span class="mono">{f"{item["ultima_km"]:,}".replace(",", ".") + " km" if item["ultima_km"] else "—"}</span>',
                f'<span class="mono">{f"{item["proxima_km"]:,}".replace(",", ".") + " km" if item["proxima_km"] else "—"}</span>',
                f'<span class="mono">{restante}</span>',
                selo_situacao(
                    {"vencida": "Vencida", "proxima": "Próxima", "em_dia": "Em dia"}[situacao],
                    situacao,
                ),
            ]
        )
    tabela_html(["Item", "Intervalo", "Última", "Próxima", "Restante", "Situação"], linhas, legenda="Plano de manutenção da moto")


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
        legenda="Histórico de manutenção da moto",
    )


def _aba_documentos(moto):
    registros = documentos.listar_por_moto(moto["id"])
    with lista_registros("motos_documentos", acoes=1):
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
            campos = [
                campo("Referência", f'<span class="fs-secundario texto-2">{escape(str(doc.get("ano_referencia") or doc.get("descricao") or "—"))}</span>'),
                campo("Vencimento", f'<span class="mono fs-secundario">{formatar_data(doc["vencimento"])}</span>'),
            ]
            with registro(
                "motos_documentos",
                doc["id"],
                f'<span class="fs-secundario">{escape(doc["tipo"].upper())}</span>',
                campos,
                selo=selo_situacao(texto_situacao, situacao),
                acoes=not doc["regularizado"],
            ) as acoes:
                if not doc["regularizado"] and botao_acao(
                    acoes, "regularizar", f"regularizar_moto_doc_{doc['id']}", ajuda=f"Marcar o documento {doc['tipo'].upper()} como regularizado"
                ):
                    _dialog_regularizar(doc)


def _aba_contratos(moto):
    registros = [c for c in contratos.listar() if c["moto_id"] == moto["id"]]
    registros.sort(key=lambda c: c["data_inicio"], reverse=True)
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    linhas = [
        [
            nomes.get(c["cliente_id"], "—"),
            f'<span class="mono">{formatar_data(c["data_inicio"])}</span>',
            f'<span class="mono">{formatar_data(c["data_encerramento"]) if c["data_encerramento"] else "<span class=texto-3>—</span>"}</span>',
            selo_situacao(
                {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}[c["status"]],
                c["status"],
            ),
            f'<span class="mono">{formatar_moeda(c["valor_periodo"])}</span>',
        ]
        for c in registros
    ]
    tabela_html(["Cliente", "Início", "Fim", "Status", "Valor / período"], linhas, legenda="Contratos da moto")


def _aba_financeiro(moto):
    resultado = relatorios.resultado_por_moto(date(1900, 1, 1), hoje_br())["resultado"]
    dados = next((r for r in resultado if r["moto_id"] == moto["id"]), None)
    if not dados:
        st.info("Sem dados financeiros para esta moto ainda.")
        return
    faixa_dados(
        [
            ("Receita recebida", f'<span class="mono">{formatar_moeda_compacta(dados["receita_recebida"])}</span>', "sucesso"),
            ("Custo de manutenção", f'<span class="mono">{formatar_moeda_compacta(dados["custo_manutencao"])}</span>'),
            ("Custo de documentos", f'<span class="mono">{formatar_moeda_compacta(dados["custo_documentos"])}</span>'),
            (
                "Resultado",
                f'<span class="mono">{formatar_moeda_compacta(dados["resultado"])}</span>',
                "sucesso" if dados["resultado"] >= 0 else "perigo",
            ),
        ],
        destaque=True,
    )
    custo_km = formatar_moeda(dados["custo_por_km"]) if dados["custo_por_km"] is not None else "—"
    st.markdown(
        f'<div class="pagina-sub">Custo por km rodado desde a aquisição: <span class="mono texto-forte">{custo_km}</span></div>',
        unsafe_allow_html=True,
    )


def _exibir_ficha(moto_id):
    moto = motos.obter(moto_id)
    if not moto:
        st.warning("Moto não encontrada.")
        _ir_para_lista()
        return

    if botao_voltar("motos", "voltar_motos"):
        _ir_para_lista()

    contrato = next((c for c in contratos.listar() if c["moto_id"] == moto_id and c["status"] == "ativo"), None)
    if moto["status"] == "alugada" and contrato:
        cliente = next((c for c in clientes.listar() if c["id"] == contrato["cliente_id"]), None)
        linha_status = f"contrato com {cliente['nome']}" if cliente else "contrato ativo"
    else:
        linha_status = _STATUS_ROTULO[moto["status"]]

    acoes = [
        {"rotulo": "Editar", "chave": "editar_moto_ficha", "ajuda": "Editar os dados da moto"},
        {"rotulo": "Atualizar km", "chave": "km_ficha", "icone": ":material/speed:", "ajuda": "Atualizar a quilometragem da moto"},
    ]
    if moto["status"] in ("disponivel", "inativa"):
        reativar = moto["status"] == "inativa"
        acoes.append(
            {
                "rotulo": "Reativar" if reativar else "Inativar",
                "chave": "alternar_moto_ficha",
                "icone": ":material/replay:" if reativar else ":material/block:",
                "ajuda": "Voltar a oferecer a moto para locação" if reativar else "Tirar a moto da frota de locação",
            }
        )
    cliques = cabecalho_ficha(
        ficha_identidade(
            escape(f"{moto['marca']} {moto['modelo']}"),
            selo=selo_situacao(
                "Alugada · " + linha_status if moto["status"] == "alugada" and contrato else linha_status,
                moto["status"],
            ),
            marca=chip_placa(moto["placa"], "grande"),
        ),
        acoes,
    )
    if cliques["editar_moto_ficha"]:
        _dialog_editar_moto(moto)
    if cliques["km_ficha"]:
        _dialog_km(moto)
    if cliques.get("alternar_moto_ficha"):
        inativando = moto["status"] != "inativa"
        with proteger():
            motos.atualizar(moto["id"], {"status": "inativa" if inativando else "disponivel"})
            feedback.concluir(mensagens.moto_status_alterado(formatar_placa(moto["placa"]), inativando))

    km_atual = f"{moto['km_atual']:,}".replace(",", ".")
    faixa_dados(
        [
            ("Km atual", f'<span class="mono">{km_atual} km</span>'),
            ("Ano fab. / modelo", f'<span class="mono">{moto.get("ano_fabricacao") or "—"} / {moto.get("ano_modelo") or "—"}</span>'),
            ("Cor", escape(str(moto.get("cor") or "—"))),
            ("Locação sugerida", f'<span class="mono">{formatar_moeda(moto.get("valor_locacao_sugerido"))} / mês</span>'),
        ]
    )

    guias = abas(
        "motos_ficha_abas",
        ["Resumo", "Plano de manutenção", "Histórico", "Documentos", "Contratos", "Financeiro"],
    )
    desenho = (_aba_resumo, _aba_plano, _aba_historico, _aba_documentos, _aba_contratos, _aba_financeiro)
    for guia, desenhar in zip(guias, desenho):
        with guia:
            if aba_ativa(guia):
                desenhar(moto)



def exibir():
    cabecalho("Motos", exibir_titulo=False)
    with proteger(nova_tentativa=True):
        visao = st.session_state.get("motos_visao", "lista")
        if visao == "ficha" and st.session_state.get("motos_id_selecionado"):
            _exibir_ficha(st.session_state["motos_id_selecionado"])
        else:
            _exibir_lista()
