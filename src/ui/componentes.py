"""Componentes compartilhados e erros sem expor dados pessoais.

Toda aparência vem de classes do design system (src/ui/estilos.css); aqui só se
monta o HTML. Não coloque cores nem tamanhos em `style=` — use as classes e tokens.
"""

from contextlib import contextmanager
from datetime import date
from html import escape

import streamlit as st

from src.domain.erros import classificar_erro
from src.ui.feedback import exibir_falha, exibir_pendentes
from src.ui.formatadores import formatar_placa

# Situação -> cor semântica. A cor de status é a única que "grita"; estados
# neutros/operacionais (alugada, aberta) só recebem o selo cinza.
_SITUACOES = {
    "vencido": "vermelho",
    "vencida": "vermelho",
    "atrasada": "vermelho",
    "atrasado": "vermelho",
    "bloqueado": "vermelho",
    "proxima": "amarelo",
    "a_vencer": "amarelo",
    "manutencao": "amarelo",
    "em_dia": "verde",
    "ok": "verde",
    "disponivel": "verde",
    "paga": "verde",
    "ativo_cliente": "verde",
    "inativa": "cinza",
    "inativo": "cinza",
    "cancelada": "cinza",
    "cancelado": "cinza",
    "ativo": "verde",
    "encerrado": "azul",
}
# Cor cheia e cor de texto por situação. Só os gráficos (canvas, sem acesso às
# variáveis CSS) usam estes hex; o HTML usa as classes abaixo.
CORES_BORDA = {
    "vermelho": "#D64545",
    "amarelo": "#F2B705",
    "verde": "#2F9E6E",
    "azul": "#3F6E9C",
    "cinza": "#9AA0A6",
}
CORES_TEXTO = {**CORES_BORDA, "amarelo": "#8a6600"}
CORES_STATUS_BORDA = {chave: CORES_BORDA[cor] for chave, cor in _SITUACOES.items()}
CORES_STATUS_TEXTO = {chave: CORES_TEXTO[cor] for chave, cor in _SITUACOES.items()}

# Cor semântica -> sufixo de classe (badge--*, alerta-item--*, seg-*)
_TOM = {"vermelho": "perigo", "amarelo": "alerta", "verde": "sucesso", "azul": "info", "cinza": "neutro"}
_SEGMENTO_POR_HEX = {
    CORES_BORDA["verde"]: "seg-sucesso",
    CORES_BORDA["vermelho"]: "seg-perigo",
    CORES_BORDA["amarelo"]: "seg-alerta",
}


def _tom_situacao(situacao):
    """Tom semântico (perigo, alerta, sucesso, neutro) de uma situação; desconhecida = neutro."""
    return _TOM.get(_SITUACOES.get(situacao), "neutro")


@contextmanager
def proteger(nova_tentativa=False):
    """Converte falhas em mensagens que dizem o que houve e o que fazer (`src.domain.erros` classifica,
    `feedback.exibir_falha` desenha). `nova_tentativa=True` nas páginas e consultas: indisponibilidade do
    serviço ganha o botão `Tentar novamente`. Em formulários (padrão) o botão de envio é a nova tentativa."""
    try:
        yield
    except Exception as erro:
        exibir_falha(classificar_erro(erro), nova_tentativa=nova_tentativa)


# ---------------------------------------------------------------- estrutura --


def cabecalho_pagina(titulo, sub=None, sobretitulo=None, lateral=None, acao=None):
    """Cabeçalho padrão de página: sobretítulo, título (h1), descrição/resumo e, opcionalmente,
    um indicador contextual (`lateral`, HTML) ou a ação primária da página.

    `acao` é um dicionário `{"rotulo", "chave", "icone"?, "ajuda"?, "formulario"?}`. O botão é
    do Streamlit (fora do HTML) e fica à direita do título no desktop; quando o cabeçalho fica
    estreito, vai para depois da descrição em largura total (ver `.st-key-pagina_cabecalho`).
    Use `"formulario": True` dentro de um `st.form` (botão de envio). Devolve True se clicado.
    Cada página tem no máximo uma ação primária aqui."""
    partes = ""
    if sobretitulo:
        partes += f'<div class="painel-sobretitulo">{escape(sobretitulo)}</div>'
    partes += f'<h1 class="rotulo pagina-titulo">{escape(titulo)}</h1>'
    if sub:
        partes += f'<div class="pagina-sub">{sub}</div>'
    if acao is None:
        st.markdown(
            f'<div class="painel-cabecalho"><div>{partes}</div>{lateral or ""}</div>',
            unsafe_allow_html=True,
        )
        return False
    with st.container(key="pagina_cabecalho"):
        st.markdown(f'<div class="pagina-cabecalho__texto">{partes}</div>', unsafe_allow_html=True)
        botao = st.form_submit_button if acao.get("formulario") else st.button
        return botao(
            acao["rotulo"],
            key=acao["chave"],
            icon=acao.get("icone", ":material/add:"),
            help=acao.get("ajuda"),
            type="primary",
        )


def ficha_identidade(titulo, selo=None, marca=None, subtitulo=None):
    """HTML da identidade de uma ficha: marca (chip de placa ou avatar, já em HTML), título (h1), subtítulo
    e selo de situação. A marca vai ao lado do texto e desce para cima dele quando falta largura."""
    texto = f'<h1 class="rotulo ficha-id__titulo">{titulo}</h1>'
    if subtitulo:
        texto += f'<div class="ficha-id__sub">{subtitulo}</div>'
    if selo:
        texto += f'<div class="ficha-id__selo">{selo}</div>'
    marca_html = f'<div class="ficha-id__marca">{marca}</div>' if marca else ""
    return f'<div class="ficha-id">{marca_html}<div class="ficha-id__texto">{texto}</div></div>'


def cabecalho_ficha(identidade, acoes=()):
    """Cabeçalho padrão das fichas (Moto, Cliente, Contrato, comparação de vistorias): identidade à
    esquerda (`ficha_identidade`) e ações da ficha à direita, nenhuma delas primária. Quando o cabeçalho
    fica estreito (consulta ao próprio contêiner, vale também em janela dividida) as ações descem para
    depois da identidade em largura total, sem perder nenhuma.

    `acoes`: lista de `{"rotulo", "chave", "icone"?, "ajuda"?, "download"?}`. Devolve `{chave: clicado}`.
    Com `"download": {"data", "file_name", "mime"}` a ação vira um botão de download (`data` pode ser
    uma função, chamada só no clique, sem recarregar a ficha); o retorno dessa chave é sempre False."""
    cliques = {}
    with st.container(key="ficha_cabecalho"):
        st.markdown(identidade, unsafe_allow_html=True)
        if acoes:
            with st.container(key="ficha_acoes"):
                for acao in acoes:
                    icone = acao.get("icone", ACOES["editar"][1])
                    if "download" in acao:
                        st.download_button(
                            acao["rotulo"],
                            key=acao["chave"],
                            icon=icone,
                            help=acao.get("ajuda"),
                            on_click="ignore",
                            **acao["download"],
                        )
                        cliques[acao["chave"]] = False
                        continue
                    cliques[acao["chave"]] = st.button(
                        acao["rotulo"],
                        key=acao["chave"],
                        icon=icone,
                        help=acao.get("ajuda"),
                    )
    return cliques


@contextmanager
def cartao_ficha(chave, titulo, acao=None):
    """Cartão de ficha com título e, opcionalmente, uma ação à direita do título (`{"rotulo", "chave",
    "icone"?, "ajuda"?}`). Cabe sempre inteiro: o botão desce para baixo do título quando falta largura,
    em vez de ser cortado. Devolve se a ação foi clicada; desenhe o corpo dentro do `with`."""
    with st.container(key=f"cartaoficha_{chave}"):
        with st.container(key=f"cartaocab_{chave}"):
            st.markdown(f'<h3 class="cartao__titulo">{escape(titulo)}</h3>', unsafe_allow_html=True)
            clicou = False
            if acao:
                clicou = st.button(
                    acao["rotulo"],
                    key=acao["chave"],
                    icon=acao.get("icone", ACOES["abrir"][1]),
                    help=acao.get("ajuda"),
                )
        yield clicou


def cartao_dados(titulo, corpo):
    """Cartão de ficha somente leitura: título e corpo (HTML). Mesmo cabeçalho de `cartao_ficha`."""
    return (
        '<div class="cartao"><div class="cartao__cab cartao__cab--fora">'
        f'<h3 class="cartao__titulo">{escape(titulo)}</h3></div>{corpo}</div>'
    )


def faixa_dados(itens, destaque=False):
    """Faixa de dados no topo das fichas: células rotuladas que ocupam a largura e quebram de linha
    quando falta espaço, sem depender da posição de cada célula (nada de `nth-child`). Cada célula
    é `(rotulo, valor_html)` ou `(rotulo, valor_html, tom)`, com `tom` em `perigo`, `sucesso` ou
    `texto-3`. O valor reduz de tamanho conforme a largura da célula, então números grandes (R$ 9.999.999)
    nunca estouram. `destaque=True` usa valores maiores (resumo financeiro)."""
    celulas = ""
    for item in itens:
        rotulo, valor = item[0], item[1]
        tom = f" faixa-dados__valor--{item[2]}" if len(item) > 2 and item[2] else ""
        celulas += (
            f'<div class="faixa-dados__item"><span class="faixa-dados__rotulo">{escape(rotulo)}</span>'
            f'<span class="faixa-dados__valor{tom}">{valor}</span></div>'
        )
    variante = " faixa-dados--destaque" if destaque else ""
    st.markdown(f'<div class="cartao faixa-dados{variante}">{celulas}</div>', unsafe_allow_html=True)


def dado(rotulo, valor_html):
    """Dado rotulado de um cartão de ficha (rótulo discreto em cima, valor embaixo), em HTML."""
    return (
        f'<div class="dado"><span class="dado__rotulo">{escape(rotulo)}</span>'
        f'<span class="dado__valor">{valor_html}</span></div>'
    )


def grade_dados(itens_html):
    """Grade de `dado(...)` que usa quantas colunas couberem (mín. ~8,5 rem cada) e quebra de linha por largura."""
    return f'<div class="grade-auto">{"".join(itens_html)}</div>'


@contextmanager
def paineis(chave, iguais=False):
    """Dois painéis lado a lado (principal e lateral) que empilham quando o contêiner perde largura útil:
    cada painel mantém pelo menos ~18 rem; abaixo disso o lateral vai para baixo do principal (a ordem de
    leitura e de tabulação é a mesma nas duas disposições). `iguais=True` dá a mesma largura aos dois
    (Entrega/Devolução). Uso: `with paineis("moto_resumo") as (principal, lateral): with principal: ...`"""
    sufixo = "__iguais" if iguais else ""
    with st.container(key=f"paineis_{chave}{sufixo}", horizontal=True, vertical_alignment="top"):
        yield st.container(key=f"painelA_{chave}"), st.container(key=f"painelB_{chave}")


def cartao_html(titulo, corpo, meta=None):
    """Cartão com cabeçalho (título + meta opcional) e corpo já em HTML."""
    cab = f'<h2 class="cartao__titulo">{escape(titulo)}</h2>'
    if meta:
        cab += f'<span class="cartao__meta">{escape(meta)}</span>'
    return (
        f'<div class="cartao cartao--sem-espaco"><div class="cartao__cab">{cab}</div>'
        f"{corpo}</div>"
    )


def estado_vazio(titulo, texto=None, compacto=False):
    """Estado vazio: ícone, título e explicação (motivo + próximo passo). No modo compacto (dentro
    de listas) vira uma linha com o título e, se houver, a explicação logo abaixo."""
    if compacto:
        descricao = f'<span class="vazio__texto">{escape(texto)}</span>' if texto else ""
        return f'<div class="vazio vazio--linha"><div><div class="vazio__titulo">{escape(titulo)}</div>{descricao}</div></div>'
    descricao = f'<div class="vazio__texto">{escape(texto)}</div>' if texto else ""
    return (
        '<div class="vazio"><div class="vazio__icone"></div>'
        f'<div class="vazio__titulo">{escape(titulo)}</div>{descricao}</div>'
    )


def vazio_lista(encontrado, ausente, tem_registros, acao=None):
    """Linha de lista vazia (HTML) que explica o motivo e o próximo passo. Com registros
    cadastrados, o filtro/busca ocultou tudo (`encontrado`); sem registros, vale `ausente` e
    aponta a `acao` de cadastro do cabeçalho.
    Ex.: `vazio_lista("Nenhuma moto encontrada.", "Ainda não há motos cadastradas.", bool(registros), "Nova moto")`."""
    if tem_registros:
        return estado_vazio(
            encontrado,
            "Nenhum resultado para o filtro ou a busca atual. Limpe a busca ou escolha outro filtro.",
            compacto=True,
        )
    passo = f"Use “{acao}”, no topo da página, para cadastrar." if acao else None
    return estado_vazio(ausente, passo, compacto=True)


def mostrar_vazio(titulo="Nenhum registro encontrado", texto=None):
    st.markdown(
        f'<div class="cartao cartao--sem-espaco">{estado_vazio(titulo, texto)}</div>',
        unsafe_allow_html=True,
    )


def kpi(rotulo, valor, contexto=None, tom=None, extra=""):
    """Indicador: rótulo pequeno, valor em destaque e contexto. `tom`='perigo' colore o valor;
    `extra` é HTML complementar (barra, legenda) abaixo do valor."""
    classe_valor = f" kpi__valor--{tom}" if tom else ""
    return (
        f'<div class="kpi"><div class="kpi__rotulo">{escape(rotulo)}</div>'
        f'<div class="kpi__linha"><span class="kpi__valor{classe_valor}">{valor}</span></div>'
        f"{extra}"
        + (f'<div class="kpi__contexto">{contexto}</div>' if contexto else "")
        + "</div>"
    )


def kpi_grade(itens_html):
    st.markdown(f'<div class="kpi-grade">{"".join(itens_html)}</div>', unsafe_allow_html=True)


def cartao_kpi(titulo, valor):
    st.metric(titulo, valor)


# ------------------------------------------------------------------ tabelas --


def tabela_html(cabecalhos, linhas, vazio=None, legenda=None):
    """Tabela somente leitura (dados tabulares sem ação por linha: plano de manutenção, históricos,
    relatórios...), hairline entre linhas, sem zebra. Cada célula de `linhas` já vem pronta como HTML
    (use selo_situacao/chip_placa/mono). `vazio` é o HTML do estado vazio (ex.: `vazio_lista(...)`);
    `legenda` é o nome da tabela para leitores de tela (visualmente oculto).

    Semântica: `<th scope="col">` e papéis ARIA explícitos (table, row, columnheader, cell), que
    continuam valendo quando o CSS transforma as linhas em cartões no celular. Cabeçalho vazio
    ("") marca uma coluna decorativa (ex.: barra de proporção), ignorada por leitores de tela.
    Interativos (com botões) usam `registro`, não esta função."""

    def celula(conteudo, tag, rotulo=None, decorativa=False, cheia=False):
        # data-label: no celular o cabeçalho some e cada célula mostra o próprio rótulo (ver estilos.css)
        atributos = f' data-label="{escape(str(rotulo), quote=True)}"' if rotulo and tag == "td" else ""
        if cheia:
            atributos += ' class="celula--cheia"'
        papel = "columnheader" if tag == "th" else "cell"
        if decorativa:
            return f'<{tag} role="{papel}" aria-hidden="true"{atributos}>{conteudo}</{tag}>'
        escopo = ' scope="col"' if tag == "th" else ""
        return f'<{tag} role="{papel}"{escopo}{atributos}>{conteudo}</{tag}>'

    ths = "".join(celula(c, "th", decorativa=not c) for c in cabecalhos)
    # Nº ímpar de colunas: no celular (2 por linha) a última ocupa a linha inteira, marcada aqui e não por posição no CSS
    impar = len(cabecalhos) % 2 == 1
    if not linhas:
        corpo = (
            f'<tr role="row"><td role="cell" colspan="{len(cabecalhos)}">'
            f'{vazio or estado_vazio("Nenhum registro encontrado.", compacto=True)}</td></tr>'
        )
    else:
        corpo = "".join(
            '<tr role="row">'
            + "".join(
                celula(valor, "td", rotulo, decorativa=not rotulo, cheia=impar and indice == len(cabecalhos) - 1)
                for indice, (rotulo, valor) in enumerate(zip(cabecalhos, linha))
            )
            + "</tr>"
            for linha in linhas
        )
    nome = f' aria-label="{escape(legenda, quote=True)}"' if legenda else ""
    legenda_html = f'<caption class="so-leitor">{escape(legenda)}</caption>' if legenda else ""
    st.markdown(
        f"""
        <div class="tabela-leitura">
          <table role="table"{nome}>
            {legenda_html}<thead role="rowgroup"><tr role="row">{ths}</tr></thead>
            <tbody role="rowgroup">{corpo}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------ selos e barras --


def selo_situacao(texto, situacao):
    """Selo de status (bolinha + texto sobre fundo suave): o estado nunca depende só da cor."""
    return f'<span class="badge badge--{_tom_situacao(situacao)}">{escape(str(texto))}</span>'


def chip_placa(placa, tamanho="normal"):
    """Chip mono de placa, como nas tabelas do mockup."""
    classe = "chip-placa chip-placa--grande" if tamanho == "grande" else "chip-placa"
    return f'<span class="mono {classe}">{escape(formatar_placa(placa))}</span>'


def item_alerta(numero, titulo, descricao, tom):
    """Linha de alerta com selo circular tracejado; `tom`: 'perigo' ou 'alerta'."""
    return (
        f'<div class="alerta-item alerta-item--{tom}"><div class="alerta-item__num">{numero}</div>'
        f'<div><div class="alerta-item__titulo">{titulo}</div>'
        f'<div class="alerta-item__descricao">{descricao}</div></div></div>'
    )


def painel_selos(itens):
    """Selos circulares tracejados (adesivo de vistoria) para alertas.

    itens: lista de (rótulo, quantidade, situação), situação em CORES_STATUS_BORDA.
    """
    if not itens:
        return
    blocos = "".join(
        f'<div class="alerta-item alerta-item--{_tom_situacao(situacao)}" style="min-width:11rem;padding:0;">'
        f'<div class="alerta-item__num">{quantidade}</div>'
        f'<span class="fs-secundario texto-2">{rotulo}</span></div>'
        for rotulo, quantidade, situacao in itens
    )
    st.markdown(f'<div class="selos-linha">{blocos}</div>', unsafe_allow_html=True)


# Classes de segmento da barra de ocupação: alugada é grafite (estado dominante,
# não é alerta), as demais seguem o token de situação.
SEGMENTOS_OCUPACAO = {
    "alugada": "seg-alugada",
    "disponivel": "seg-disponivel",
    "manutencao": "seg-manutencao",
    "inativa": "seg-inativa",
}


def barra_segmentada(segmentos):
    """HTML da barra segmentada. segmentos: lista de (largura_percentual, status)."""
    itens = "".join(
        f'<i class="{SEGMENTOS_OCUPACAO[s]}" style="width:{largura}%"></i>'
        for largura, s in segmentos
        if largura > 0
    )
    # Decorativa: o mesmo dado vem escrito na legenda e no contexto do indicador
    return f'<div class="barra" aria-hidden="true">{itens}</div>'


def legenda_ocupacao(itens):
    """Legenda com quadradinho colorido. itens: lista de (texto, status)."""
    return '<div class="kpi__legenda">' + "".join(
        f'<div class="kpi__legenda-item {SEGMENTOS_OCUPACAO[s]}">{texto}</div>' for texto, s in itens
    ) + "</div>"


def barra_ocupacao(segmentos):
    """Barra segmentada (medidor de combustível) em vez de gráfico de biblioteca.

    segmentos: lista de (rótulo, quantidade, status), status em SEGMENTOS_OCUPACAO.
    """
    partes = [(r, q, s) for r, q, s in segmentos if q]
    if not partes:
        st.caption("Sem motos cadastradas para exibir ocupação.")
        return
    barra = "".join(
        f'<i class="{SEGMENTOS_OCUPACAO.get(s, "seg-inativa")}" style="flex:{q}"></i>'
        for _, q, s in partes
    )
    legenda = legenda_ocupacao([(f"{rotulo} ({q})", s) for rotulo, q, s in partes])
    st.markdown(
        f'<div class="barra" style="margin:.6rem 0 .5rem;" aria-hidden="true">{barra}</div>{legenda}',
        unsafe_allow_html=True,
    )


def barra_proporcional(percentual, cor="#2F9E6E"):
    """Barra de 100px (6px de altura) para tabelas de Relatórios, em vez de gráfico
    de biblioteca. `percentual` de 0 a 100; `cor` é um dos hex de CORES_BORDA (ou grafite)."""
    largura = max(0, min(100, int(percentual)))
    segmento = _SEGMENTO_POR_HEX.get(cor, "seg-alugada")
    return f'<div class="barra barra--fina {segmento}"><i style="width:{largura}%"></i></div>'


def indicador_etapas(atual, rotulos, nome="Etapas"):
    """Indicador do assistente (Novo contrato): lista ordenada de etapas, com círculos numerados
    conectados por linha. A etapa atual leva `aria-current="step"` e as concluídas dizem “concluída”
    para leitores de tela. Em tela estreita só o rótulo da etapa atual aparece nos círculos, e a
    linha de resumo (“Etapa 2 de 4: Moto”) segue sempre visível, então nenhum rótulo estoura a largura."""
    itens = ""
    for i, rotulo in enumerate(rotulos, start=1):
        estado = "concluida" if i < atual else ("atual" if i == atual else "futura")
        marca = ' aria-current="step"' if i == atual else ""
        aviso = '<span class="so-leitor"> (concluída)</span>' if i < atual else ""
        itens += (
            f'<li class="etapa etapa--{estado}"{marca}><span class="etapa__num">{i}</span>'
            f'<span class="etapa__rotulo">{escape(rotulo)}{aviso}</span></li>'
        )
    resumo = f"Etapa {atual} de {len(rotulos)}: {escape(rotulos[atual - 1])}"
    st.markdown(
        f'<nav class="etapas" aria-label="{escape(nome, quote=True)}"><ol class="etapas__lista">{itens}</ol>'
        f'<p class="etapas__resumo">{resumo}</p></nav>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------- ações --

# Vocabulário único de ações por linha: a mesma ação tem sempre o mesmo texto e o mesmo
# ícone (conjunto Material do Streamlit) em todas as páginas.
ACOES = {
    "abrir": ("Abrir", ":material/arrow_forward:"),
    "editar": ("Editar", ":material/edit:"),
    "pagar": ("Pagar", ":material/payments:"),
    "concluir": ("Concluir", ":material/check:"),
    "cancelar": ("Cancelar", ":material/close:"),
    "remover": ("Remover", ":material/delete:"),
    "regularizar": ("Regularizar", ":material/task_alt:"),
    "comprovante": ("Comprovante", ":material/receipt_long:"),
    "km": ("Atualizar km", ":material/speed:"),
    "comparar": ("Comparar", ":material/compare_arrows:"),
    "selecionar": ("Selecionar", ":material/radio_button_unchecked:"),
    "voltar": ("Voltar", ":material/arrow_back:"),
}


def botao_acao(alvo, acao, chave, ajuda=None, rotulo=None, desabilitado=False, on_click=None, args=None, icone=None):
    """Botão de ação de um registro: ícone + texto sempre visíveis (o texto também é a dica,
    `help`). Devolve True quando clicado. `alvo` é o grupo de ações do registro
    (`registro(...) as acoes`), uma coluna/container ou `st`; `ajuda` detalha o alvo da ação
    (ex.: a placa). `on_click`/`args` rodam antes da reexecução (útil em diálogos)."""
    padrao, icone_padrao = ACOES[acao]
    texto = rotulo or padrao
    return alvo.button(
        texto,
        key=chave,
        icon=icone or icone_padrao,
        help=ajuda or texto,
        type="tertiary",
        disabled=desabilitado,
        on_click=on_click,
        args=args,
    )


def botao_voltar(destino, chave):
    """Retorno contextual das fichas e do assistente: seta + `Voltar para <destino>`."""
    return st.button(f"Voltar para {destino}", key=chave, icon=ACOES["voltar"][1], type="tertiary")


# ---------------------------------------------------------------- navegação --


def selecionar(titulo, linhas, rotulo, chave):
    if not linhas:
        st.info(f"Nenhum registro disponível para {titulo.lower()}.")
        return None
    mapa = {r["id"]: r for r in linhas}
    escolhido = st.selectbox(
        titulo,
        list(mapa),
        format_func=lambda identificador: rotulo(mapa[identificador]),
        key=chave,
    )
    return mapa[escolhido]


def abrir_ficha_contrato(contrato_id):
    """Abre a página de contratos com a ficha indicada já selecionada."""
    st.session_state.pop("contratos_ficha_abas_indice", None)  # ficha nova abre na primeira aba
    st.session_state["contratos_visao"] = "ficha"
    st.session_state["contratos_id_selecionado"] = contrato_id
    st.switch_page("pages/4_Contratos.py")


def abrir_ficha_cliente(cliente_id):
    """Abre a página de clientes com a ficha indicada já selecionada."""
    st.session_state.pop("clientes_ficha_abas_indice", None)
    st.session_state["clientes_visao"] = "ficha"
    st.session_state["clientes_id_selecionado"] = cliente_id
    st.switch_page("pages/3_Clientes.py")


def campo_data(titulo, valor=None, **kwargs):
    return st.date_input(
        titulo,
        value=date.fromisoformat(valor[:10]) if valor else None,
        format="DD/MM/YYYY",
        **kwargs,
    )


def cabecalho(titulo, exibir_titulo=True):
    from src.auth import require_login
    from src.ui.tema import aplicar

    # O app.py já aplica tema e login; a página só refaz isso se for executada sozinha.
    if not st.session_state.get("shell_pronto"):
        aplicar()
        require_login()
    if exibir_titulo:
        st.title(titulo)
    exibir_pendentes()
