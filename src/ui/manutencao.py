"""Manutenção: alertas, histórico e catálogo — segue Manutencao.dc.html do mockup."""

from datetime import date
from decimal import Decimal
from html import escape

import streamlit as st

from src.services import manutencao, motos, alertas
from src.domain import mensagens
from src.domain.entradas import decimal_campo, erro_de, primeiro_erro
from src.domain.valores import hoje_br
from src.domain.manutencao_regras import preparar_itens_adicionais
from src.ui.componentes import (
    cabecalho,
    cabecalho_pagina,
    vazio_lista,
    proteger,
    selecionar,
    chip_placa,
    selo_situacao,
    tabela_html,
    botao_acao,
)
from src.ui import feedback
from src.ui.formularios import (
    campo_inteiro,
    campo_moeda,
    legenda_obrigatorios,
    linha_campos,
    rodape_formulario,
    rotulo_obrigatorio,
)
from src.ui.listas import abas, aba_ativa, barra_filtros, paginar, rodape_paginacao
from src.domain.formatadores import formatar_data, formatar_moeda, formatar_placa
from src.ui.registros import campo, lista_registros, registro

_SITUACAO_ROTULO = {"vencida": "Vencida", "proxima": "Próxima"}
_FILTROS_ALERTA = [("todas", "Todas"), ("vencida", "Vencidas"), ("proxima", "Próximas")]
_FILTROS_TIPO = [("todas", "Todas"), ("preventiva", "Preventiva"), ("corretiva", "Corretiva")]
_STATUS_ROTULO = {"aberta": "Aberta", "concluida": "Concluída", "cancelada": "Cancelada"}
# "aberta" é estado operacional (sem tinta); concluída usa o verde de "ok".
_STATUS_SELO = {"aberta": "aberta", "concluida": "ok", "cancelada": "cancelada"}
_PREFIXO_REGISTRO = "manreg_"
_CHAVE_EXTRAS = _PREFIXO_REGISTRO + "extras_ids"


def _km(valor):
    return f"{int(valor):,} km".replace(",", ".") if valor is not None else "—"


def _mono(texto, classe=""):
    return f'<span class="mono fs-secundario {classe}">{texto}</span>'


def _texto(texto, classe=""):
    return f'<span class="fs-secundario {classe}">{texto}</span>'


def _valor_tolerante(texto, positivo=False):
    """Valor para a prévia ao vivo: entrada inválida conta como zero (o erro
    aparece junto ao botão de salvar, via decimal_campo)."""
    try:
        return decimal_campo(texto, "Campo", positivo=positivo)
    except ValueError:
        return Decimal("0.00")


def _limpar_registro():
    for chave in [c for c in st.session_state if str(c).startswith(_PREFIXO_REGISTRO)]:
        del st.session_state[chave]


def _adicionar_linha():
    ids = st.session_state.setdefault(_CHAVE_EXTRAS, [])
    ids.append(max(ids, default=-1) + 1)


def _remover_linha(n):
    st.session_state[_CHAVE_EXTRAS].remove(n)


def _linhas_adicionais():
    """Peças e serviços fora do plano: um grupo de campos por item (com rótulos visíveis e botão
    `Remover`), no lugar da tabela editável em canvas, que não segue o tema nem funciona bem no celular.
    Adicionar e remover são callbacks (rodam antes da reexecução, também dentro do diálogo).
    Devolve os registros no formato de `preparar_itens_adicionais`."""
    ids = st.session_state.setdefault(_CHAVE_EXTRAS, [])
    st.caption("Outras peças ou serviços")
    registros = []
    for n in ids:
        with st.container(border=True, key=f"{_PREFIXO_REGISTRO}extra_grupo_{n}"):
            descricao = st.text_input("Descrição", key=f"{_PREFIXO_REGISTRO}extra_desc_{n}")
            with linha_campos([1, 1, 1], f"man_extra_{n}", vertical_alignment="bottom") as (c_qtd, c_valor, c_remover):
                quantidade = c_qtd.text_input("Quantidade", "1", key=f"{_PREFIXO_REGISTRO}extra_qtd_{n}")
                with c_valor:
                    valor = campo_moeda("Valor unitário", 0, f"{_PREFIXO_REGISTRO}extra_valor_{n}", ao_vivo=True)
                botao_acao(
                    c_remover,
                    "remover",
                    f"{_PREFIXO_REGISTRO}extra_remover_{n}",
                    ajuda=f"Remover {descricao.strip() or 'esta linha'} da lista de peças e serviços",
                    on_click=_remover_linha,
                    args=(n,),
                )
        registros.append({"descricao": descricao, "quantidade": quantidade, "valor_unitario": valor})
    st.button(
        "Adicionar peça ou serviço",
        key=_PREFIXO_REGISTRO + "extra_adicionar",
        icon=":material/add:",
        on_click=_adicionar_linha,
    )
    return registros


def _leitura(rotulo, valor_html):
    """Valor calculado (não editável), com o mesmo rótulo e altura dos campos ao lado."""
    return (
        f'<div class="leitura"><span class="leitura__rotulo">{escape(rotulo)}</span>'
        f'<span class="leitura__valor">{valor_html}</span></div>'
    )


@st.dialog("Registrar manutenção", width="large")
def _dialog_registrar():
    frota = [m for m in motos.listar() if m["status"] != "inativa"]
    itens = [i for i in manutencao.listar_catalogo() if i["ativo"]]
    if not frota:
        st.info("Cadastre uma moto ativa antes de registrar manutenções.")
        return

    moto = selecionar(
        "Moto",
        frota,
        lambda m: f"{m['placa']} · {m['marca']} {m['modelo']}",
        _PREFIXO_REGISTRO + "moto",
    )
    with linha_campos([1, 1], "man_tipo_status") as (col_tipo, col_status):
        tipo = col_tipo.radio(
            "Tipo", ["Preventiva", "Corretiva"], horizontal=True, key=_PREFIXO_REGISTRO + "tipo"
        ).lower()
        status_rotulo = col_status.radio(
            "Status", ["Concluída", "Aberta"], horizontal=True, key=_PREFIXO_REGISTRO + "status"
        )
    concluida = status_rotulo == "Concluída"

    with linha_campos([1, 1], "man_datas") as (col_entrada, col_saida):
        entrada = col_entrada.date_input(
            "Data de entrada", hoje_br(), format="DD/MM/YYYY", key=_PREFIXO_REGISTRO + "entrada"
        )
        saida = col_saida.date_input(
            "Data de saída",
            entrada,
            min_value=entrada,
            format="DD/MM/YYYY",
            disabled=not concluida,
            key=_PREFIXO_REGISTRO + "saida",
            help=None if concluida else "A data de saída só vale para manutenção concluída.",
        )
    with linha_campos([1, 2], "man_km_oficina") as (col_km, col_oficina):
        with col_km:
            km = campo_inteiro(
                "Km",
                moto["km_atual"],
                f"{_PREFIXO_REGISTRO}km_{moto['id']}",
                sufixo="km",
                minimo=moto["km_atual"],
            )
        oficina = col_oficina.text_input("Oficina", key=_PREFIXO_REGISTRO + "oficina")
    descricao = st.text_area(rotulo_obrigatorio("Descrição"), height=80, key=_PREFIXO_REGISTRO + "descricao")

    escolhidos = st.multiselect(
        "Itens do plano substituídos ou revisados",
        [i["id"] for i in itens],
        format_func=lambda id: next(i["nome"] for i in itens if i["id"] == id),
        key=_PREFIXO_REGISTRO + "itens",
        help="Itens marcados aqui zeram o contador do plano da moto.",
    )
    linhas_plano = []
    for id in escolhidos:
        item = next(i for i in itens if i["id"] == id)
        with st.container(border=True, key=f"{_PREFIXO_REGISTRO}plano_{id}"):
            st.markdown(
                _texto(escape(item["nome"])) + ' <span class="texto-3 fs-legenda">(plano)</span>',
                unsafe_allow_html=True,
            )
            with linha_campos([1, 1, 1], f"man_plano_{id}", vertical_alignment="bottom") as (c_qtd, c_valor, c_sub):
                qtd = c_qtd.text_input("Quantidade", "1", key=f"{_PREFIXO_REGISTRO}qtd_{id}")
                with c_valor:
                    valor = campo_moeda("Valor unitário", 0, f"{_PREFIXO_REGISTRO}valor_{id}", ao_vivo=True)
                subtotal = _valor_tolerante(qtd, positivo=True) * _valor_tolerante(valor)
                c_sub.markdown(_leitura("Subtotal", formatar_moeda(subtotal)), unsafe_allow_html=True)
        linhas_plano.append((item, qtd, valor, subtotal))

    registros_adicionais = _linhas_adicionais()

    mao_obra = campo_moeda("Custo de mão de obra", 0, _PREFIXO_REGISTRO + "mao_obra", ao_vivo=True)
    pecas = sum((s for *_, s in linhas_plano), Decimal("0.00")) + sum(
        (
            _valor_tolerante(str(r.get("quantidade") or "1"), positivo=True)
            * _valor_tolerante(str(r.get("valor_unitario") or "0"))
            for r in registros_adicionais
            if str(r.get("descricao") or "").strip()
        ),
        Decimal("0.00"),
    )
    total = pecas + _valor_tolerante(mao_obra)
    st.markdown(
        '<div class="resumo-custos">'
        f'<div class="leitura"><span class="leitura__rotulo">Custo de peças</span><span class="leitura__valor">{formatar_moeda(pecas)}</span></div>'
        f'<div class="leitura leitura--total"><span class="leitura__rotulo">Custo total</span><span class="leitura__valor">{formatar_moeda(total)}</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    cobrar = st.checkbox(
        "Cobrar do cliente (gera cobrança de dano no contrato vigente)",
        key=_PREFIXO_REGISTRO + "cobrar",
    )
    legenda_obrigatorios()

    erro = primeiro_erro(
        None if descricao.strip() else "Descrição: informe o serviço realizado.",
        erro_de(decimal_campo, mao_obra, "Custo de mão de obra"),
        *(
            erro_de(decimal_campo, qtd, f"Quantidade de {item['nome']}", positivo=True)
            or erro_de(decimal_campo, valor, f"Valor unitário de {item['nome']}")
            for item, qtd, valor, _ in linhas_plano
        ),
        erro_de(preparar_itens_adicionais, registros_adicionais),
    )
    acao = rodape_formulario("Salvar manutenção", "manreg", desabilitado=bool(erro), motivo=erro)
    if acao.cancelou:
        _limpar_registro()
        st.rerun()
    if acao.confirmou:
        with proteger():
            lista = [
                {
                    "item_id": item["id"],
                    "descricao": item["nome"],
                    "quantidade": decimal_campo(qtd, f"Quantidade de {item['nome']}", positivo=True),
                    "valor_unitario": decimal_campo(valor, f"Valor unitário de {item['nome']}"),
                }
                for item, qtd, valor, _ in linhas_plano
            ]
            lista.extend(preparar_itens_adicionais(registros_adicionais))
            custo_mao_obra = decimal_campo(mao_obra, "Custo de mão de obra")
            chave = feedback.chave_operacao(
                "manreg",
                [moto["id"], tipo, entrada, km, descricao, concluida, saida, oficina, custo_mao_obra, cobrar, lista],
            )
            manutencao.registrar_manutencao(
                moto["id"],
                tipo,
                entrada,
                km,
                descricao,
                status="concluida" if concluida else "aberta",
                data_saida=saida if concluida else None,
                oficina=oficina,
                custo_mao_obra=custo_mao_obra,
                cobrar_do_cliente=cobrar,
                itens=lista,
                chave_operacao=chave,
            )
            custo_total = custo_mao_obra + sum(
                (item["quantidade"] * item["valor_unitario"] for item in lista), Decimal("0")
            )
            _limpar_registro()
            feedback.concluir(
                mensagens.manutencao_registrada(formatar_placa(moto["placa"]), concluida, custo_total), "manreg"
            )


_IMPACTO_FINALIZAR = {
    "concluida": (
        "Ao concluir, a quilometragem é registrada, o plano de manutenção dos itens feitos "
        "é reiniciado e a moto sai de manutenção quando não houver outro serviço aberto."
    ),
    "cancelada": (
        "Ao cancelar, o serviço deixa de ser contado: o plano de manutenção não é reiniciado "
        "e nada é cobrado do cliente. A moto sai de manutenção quando não houver outro serviço aberto. "
        "Não é possível reabrir a manutenção depois."
    ),
}


def _finalizar_manutencao(registro, moto, acao):
    """Corpo compartilhado dos diálogos Concluir e Cancelar manutenção. Concluir é um formulário
    simples; cancelar é destrutivo (não pode ser desfeito), então mostra o registro afetado e só
    libera o botão depois de a pessoa marcar que entendeu o impacto."""
    concluir = acao == "concluida"
    entrada = date.fromisoformat(str(registro["data_entrada"])[:10])
    st.markdown(chip_placa(moto["placa"]), unsafe_allow_html=True)
    st.write(f"{formatar_data(registro['data_entrada'])} · {registro['descricao']}")
    piso = max(moto["km_atual"], registro["km"])
    rotulo_data = "Data de conclusão" if concluir else "Data do cancelamento"
    rotulo_km = "Km na conclusão" if concluir else "Km atual da moto"
    inicio_data = max(hoje_br(), entrada)
    if concluir:
        st.caption(_IMPACTO_FINALIZAR[acao])
        with st.form("form_concluir_" + registro["id"]):
            data_saida = st.date_input(
                rotulo_data, inicio_data, min_value=entrada, format="DD/MM/YYYY", key="manfin_data"
            )
            km = campo_inteiro(rotulo_km, piso, "manfin_km", sufixo="km", minimo=piso)
            resultado = rodape_formulario("Concluir manutenção", "manfin", formulario=True)
    else:
        st.markdown(
            '<div class="impacto" role="group" aria-label="O que o cancelamento altera">'
            '<div class="impacto__titulo">O que acontece ao cancelar</div>'
            f"<ul><li>{escape(_IMPACTO_FINALIZAR[acao])}</li></ul></div>",
            unsafe_allow_html=True,
        )
        data_saida = st.date_input(
            rotulo_data, inicio_data, min_value=entrada, format="DD/MM/YYYY", key="manfin_data"
        )
        km = campo_inteiro(rotulo_km, piso, "manfin_km", sufixo="km", minimo=piso)
        entendeu = st.checkbox(
            "Entendo que o cancelamento não pode ser desfeito.", key="manfin_confirma"
        )
        resultado = rodape_formulario(
            "Cancelar manutenção",
            "manfin",
            perigo=True,
            desabilitado=not entendeu,
            motivo="Marque a confirmação acima para cancelar a manutenção.",
            cancelar="Manter manutenção",
        )
    if resultado.cancelou:
        st.rerun()
    if resultado.confirmou:
        with proteger():
            manutencao.finalizar(registro["id"], acao, data_saida, km)
            feedback.concluir(mensagens.manutencao_finalizada(formatar_placa(moto["placa"]), concluir))


@st.dialog("Concluir manutenção")
def _dialog_concluir(registro, moto):
    _finalizar_manutencao(registro, moto, "concluida")


@st.dialog("Cancelar manutenção")
def _dialog_cancelar(registro, moto):
    _finalizar_manutencao(registro, moto, "cancelada")


@st.dialog("Item do catálogo")
def _dialog_item(item):
    with st.form("form_catalogo_" + item.get("id", "novo")):
        nome = st.text_input(rotulo_obrigatorio("Nome"), item.get("nome", ""))
        with linha_campos([1, 1], "man_intervalos") as (col_km, col_dias):
            with col_km:
                km = campo_inteiro(
                    "Intervalo em km", item.get("intervalo_km") or 0, "item_km", sufixo="km",
                    ajuda="Use 0 quando o item não tiver limite em km.",
                )
            with col_dias:
                dias = campo_inteiro(
                    "Intervalo em dias", item.get("intervalo_dias") or 0, "item_dias", sufixo="dias",
                    ajuda="Use 0 quando o item não tiver limite em dias.",
                )
        minimo = campo_inteiro(
            "Alerta a partir de", item.get("intervalo_minimo_km") or 0, "item_km_minimo", sufixo="km",
            ajuda="Para itens com faixa (ex.: kit de tração, de 3.000 a 5.000 km): o intervalo em km é o "
            "máximo e este é o mínimo, quando o alerta começa. Use 0 para avisar só pela antecedência "
            "das Configurações.",
        )
        ativo = st.checkbox("Ativo", item.get("ativo", True))
        legenda_obrigatorios()
        acao = rodape_formulario("Salvar item", "item", formulario=True)
        if acao.cancelou:
            st.rerun()
        if acao.confirmou:
            with proteger():
                if not nome.strip():
                    raise ValueError("Nome: informe o nome do item.")
                if not (km or dias):
                    raise ValueError("Intervalo: informe km, dias ou os dois (0 significa sem limite).")
                dados = {
                    "nome": nome,
                    "intervalo_km": km or None,
                    "intervalo_minimo_km": minimo or None,
                    "intervalo_dias": dias or None,
                    "ativo": ativo,
                }
                if item:
                    manutencao.atualizar_item_catalogo(item["id"], dados)
                else:
                    manutencao.criar_item_catalogo(dados)
                feedback.concluir(mensagens.item_catalogo_salvo(nome.strip(), novo=not item))


# ------------------------------------------------------------------ abas --

def _restante(alerta):
    partes = []
    negativo = False
    if alerta.get("km_restantes") is not None:
        partes.append(_km(alerta["km_restantes"]))
        negativo = negativo or alerta["km_restantes"] < 0
    if alerta.get("dias_restantes") is not None:
        partes.append(f"{alerta['dias_restantes']} dias")
        negativo = negativo or alerta["dias_restantes"] < 0
    cor = "texto-perigo" if negativo else ""
    return f'<span class="mono {cor}">{" / ".join(partes) or "—"}</span>'


def _aba_alertas(pendentes):
    contagem = {
        "todas": len(pendentes),
        "vencida": sum(a["situacao"] == "vencida" for a in pendentes),
        "proxima": sum(a["situacao"] == "proxima" for a in pendentes),
    }
    filtros = barra_filtros("manutencao_alertas", _FILTROS_ALERTA, padrao="todas", contagens=contagem)
    visiveis = [a for a in pendentes if filtros.valor == "todas" or a["situacao"] == filtros.valor]
    filtros.resumo(len(visiveis), ("alerta", "alertas"))
    visiveis.sort(
        key=lambda a: (
            a["situacao"] != "vencida",
            a["km_restantes"] if a.get("km_restantes") is not None else float("inf"),
        )
    )
    linhas = []
    for a in visiveis:
        proxima = " / ".join(
            filter(
                None,
                [
                    _km(a["proxima_km"]) if a.get("proxima_km") is not None else None,
                    formatar_data(a["proxima_data"]) if a.get("proxima_data") else None,
                ],
            )
        )
        linhas.append(
            [
                chip_placa(a["placa"]),
                a["item"],
                f'<span class="mono">{_km(a["km_atual"])}</span>',
                f'<span class="mono">{proxima or "—"}</span>',
                _restante(a),
                selo_situacao(_SITUACAO_ROTULO[a["situacao"]], a["situacao"]),
            ]
        )
    tabela_html(
        ["Moto", "Item", "Km atual", "Próxima", "Restante", "Situação"],
        linhas,
        legenda="Alertas de manutenção",
        vazio=vazio_lista(
            "Nenhum alerta neste filtro.",
            "Nenhuma manutenção vencida ou próxima.",
            bool(pendentes),
        ),
    )


def _aba_historico(frota):
    todos = sorted(manutencao.listar_manutencoes(), key=lambda m: m["data_entrada"], reverse=True)
    contagem = {
        "todas": len(todos),
        "preventiva": sum(m["tipo"] == "preventiva" for m in todos),
        "corretiva": sum(m["tipo"] == "corretiva" for m in todos),
    }
    filtros = barra_filtros(
        "manutencao_historico",
        _FILTROS_TIPO,
        padrao="todas",
        contagens=contagem,
        grupo="Tipo",
        busca="Buscar por moto ou oficina",
    )
    busca = filtros.busca.casefold()

    filtrados = [
        m
        for m in todos
        if (filtros.valor == "todas" or m["tipo"] == filtros.valor)
        and busca in f"{frota.get(m['moto_id'], {}).get('placa', '')} {m.get('oficina') or ''}".casefold()
    ]
    filtros.resumo(len(filtrados), ("manutenção", "manutenções"))
    pagina_atual, pagina = paginar("manutencao_historico", filtrados)

    st.write("")
    with lista_registros("manutencao_historico", acoes=2):
        if not pagina_atual:
            st.markdown(
                vazio_lista("Nenhuma manutenção encontrada.", "Ainda não há manutenções registradas.", bool(todos), "Registrar manutenção"),
                unsafe_allow_html=True,
            )
        for registro_man in pagina_atual:
            moto = frota.get(registro_man["moto_id"])
            aberta = registro_man["status"] == "aberta" and moto
            campos = [
                campo("Data", _mono(formatar_data(registro_man["data_entrada"]))),
                campo("Tipo", _texto(registro_man["tipo"].capitalize())),
                campo("Oficina", _texto(escape(registro_man.get("oficina") or "—"), "texto-2")),
                campo("Custo", _mono(formatar_moeda(registro_man["custo_total"]))),
                campo("Descrição", _texto(escape(registro_man["descricao"])), largo=True),
            ]
            with registro(
                "manutencao_historico",
                registro_man["id"],
                chip_placa(moto["placa"]) if moto else "—",
                campos,
                selo=selo_situacao(_STATUS_ROTULO[registro_man["status"]], _STATUS_SELO[registro_man["status"]]),
                acoes=bool(aberta),
            ) as acoes:
                if aberta:
                    # Duas ações distintas: concluir e cancelar nunca dividem o mesmo botão
                    if botao_acao(
                        acoes,
                        "concluir",
                        f"concluir_man_{registro_man['id']}",
                        ajuda=f"Concluir a manutenção da moto {formatar_placa(moto['placa'])}",
                    ):
                        _dialog_concluir(registro_man, moto)
                    if botao_acao(
                        acoes,
                        "cancelar",
                        f"cancelar_man_{registro_man['id']}",
                        ajuda=f"Cancelar a manutenção da moto {formatar_placa(moto['placa'])}",
                    ):
                        _dialog_cancelar(registro_man, moto)
    rodape_paginacao("manutencao_historico", pagina)


def _aba_catalogo(itens):
    _, col_botao = st.columns([5, 1])
    with col_botao:
        if st.button("+ Novo item", key="man_novo_item", use_container_width=True):
            _dialog_item({})
    st.write("")
    with lista_registros("manutencao_catalogo", acoes=1):
        if not itens:
            st.markdown(
                vazio_lista("Nenhum item no catálogo.", "Ainda não há itens no catálogo.", False),
                unsafe_allow_html=True,
            )
        for item in itens:
            muted = "" if item["ativo"] else "texto-2"
            campos = [
                campo(
                    "Intervalo km",
                    _mono(_km(item["intervalo_km"]), muted) if item["intervalo_km"] else _texto("—", "texto-3"),
                ),
                campo(
                    "Alerta a partir de",
                    _mono(_km(item["intervalo_minimo_km"]), muted)
                    if item.get("intervalo_minimo_km")
                    else _texto("—", "texto-3"),
                ),
                campo(
                    "Intervalo dias",
                    _mono(str(item["intervalo_dias"]), muted) if item["intervalo_dias"] else _texto("—", "texto-3"),
                ),
            ]
            with registro(
                "manutencao_catalogo",
                item["id"],
                _texto(escape(item["nome"]), muted),
                campos,
                selo=selo_situacao("Ativo" if item["ativo"] else "Inativo", "ativo" if item["ativo"] else "inativo"),
            ) as acoes:
                if botao_acao(acoes, "editar", f"editar_item_{item['id']}", ajuda=f"Editar o item {item['nome']}"):
                    _dialog_item(item)


# ---------------------------------------------------------------- página --

def exibir():
    cabecalho("Manutenção", exibir_titulo=False)
    with proteger(nova_tentativa=True):
        frota = {m["id"]: m for m in motos.listar()}
        pendentes = [a for a in alertas.listar_manutencao() if a["situacao"] in _SITUACAO_ROTULO]
        vencidas = sum(a["situacao"] == "vencida" for a in pendentes)
        proximas = len(pendentes) - vencidas

        if cabecalho_pagina(
            "Manutenção",
            sub=f"{vencidas} vencida(s) · {proximas} próxima(s)",
            acao={"rotulo": "Registrar manutenção", "chave": "manutencao_registrar"},
        ):
            _dialog_registrar()

        guias = abas("manutencao_abas", ["Alertas", "Histórico", "Catálogo"])
        desenho = (
            lambda: _aba_alertas(pendentes),
            lambda: _aba_historico(frota),
            lambda: _aba_catalogo(manutencao.listar_catalogo()),
        )
        for guia, desenhar in zip(guias, desenho):
            with guia:
                if aba_ativa(guia):
                    desenhar()
