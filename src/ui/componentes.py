"""Componentes compartilhados e erros sem expor dados pessoais.

Toda aparência vem de classes do design system (src/ui/estilos.css); aqui só se
monta o HTML. Não coloque cores nem tamanhos em `style=` — use as classes e tokens.
"""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from html import escape
from math import ceil
import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from src.ui.formatadores import formatar_data, formatar_moeda, formatar_placa, mascarar_cpf

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
# Cor cheia e cor de texto por situação. Só a tabela `st.dataframe` (canvas, sem
# acesso às variáveis CSS) e os gráficos usam estes hex; o HTML usa as classes abaixo.
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
def proteger():
    try:
        yield
    except ValueError as erro:
        st.error(str(erro))
    except APIError as erro:
        mensagens = {
            "23505": "Este registro já existe. Atualize a lista antes de tentar novamente.",
            "23514": "Confira datas, valores e situação do cadastro.",
            "23503": "Há registros vinculados ou uma referência deixou de existir. Atualize a página.",
            "42501": "Sua sessão não tem permissão para esta operação. Entre novamente.",
            "PGRST202": "Aplique as migrations mais recentes no banco. Consulte o guia de instalação.",
        }
        st.error(
            mensagens.get(
                erro.code,
                "Não foi possível concluir a operação. Confira os dados e atualize a página.",
            )
        )
    except Exception:
        st.error(
            "Não foi possível acessar o serviço. Verifique a conexão e a configuração do Supabase e tente novamente."
        )


# ---------------------------------------------------------------- estrutura --


def cabecalho_pagina(titulo, sub=None, sobretitulo=None, lateral=None):
    """Cabeçalho padrão de página: sobretítulo, título (h1), subtítulo e bloco lateral opcional (HTML)."""
    partes = ""
    if sobretitulo:
        partes += f'<div class="painel-sobretitulo">{escape(sobretitulo)}</div>'
    partes += f'<h1 class="rotulo pagina-titulo">{escape(titulo)}</h1>'
    if sub:
        partes += f'<div class="pagina-sub">{sub}</div>'
    st.markdown(
        f'<div class="painel-cabecalho"><div>{partes}</div>{lateral or ""}</div>',
        unsafe_allow_html=True,
    )


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
    """Estado vazio: ícone, título e descrição curta (ou uma linha compacta dentro de listas)."""
    if compacto:
        return f'<div class="vazio vazio--linha">{escape(titulo)}</div>'
    descricao = f'<div class="vazio__texto">{escape(texto)}</div>' if texto else ""
    return (
        '<div class="vazio"><div class="vazio__icone"></div>'
        f'<div class="vazio__titulo">{escape(titulo)}</div>{descricao}</div>'
    )


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


def tabela(linhas, chave="tabela", colunas=None):
    if not linhas:
        mostrar_vazio()
        return
    pagina = 1
    paginas = ceil(len(linhas) / 25)
    if paginas > 1:
        if st.session_state.get(chave + "_pagina", 1) > paginas:
            st.session_state[chave + "_pagina"] = paginas
        pagina = st.number_input(
            "Página", min_value=1, max_value=paginas, value=1, key=chave + "_pagina"
        )
    st.caption(f"{len(linhas)} registro(s) • página {pagina} de {paginas}")
    registros = []
    for linha in linhas[(pagina - 1) * 25 : pagina * 25]:
        registro = {}
        for nome, valor in linha.items():
            if (
                nome.startswith("_")
                or nome == "id"
                or nome.endswith("_id")
                or (colunas and nome not in colunas)
                or isinstance(valor, (dict, list))
            ):
                continue
            if nome == "cpf":
                valor = mascarar_cpf(valor or "")
            elif nome == "placa":
                valor = formatar_placa(valor) if valor else valor
            elif nome in {"situacao", "status"} and valor:
                valor = f"● {str(valor).replace('_', ' ')}"
            elif isinstance(valor, Decimal) or nome in {
                "valor",
                "saldo",
                "valor_pago",
                "valor_periodo",
                "custo_total",
                "custo_pecas",
                "custo_mao_obra",
                "receita_recebida",
                "custo_manutencao",
                "custo_documentos",
                "resultado",
                "custo_por_km",
                "valor_aquisicao",
                "valor_locacao_sugerido",
                "caucao_valor",
                "multa_juros",
            }:
                valor = formatar_moeda(valor) if valor is not None else "—"
            elif (
                isinstance(valor, date)
                or nome.startswith("data_")
                or nome in {"vencimento", "cnh_validade", "ultima_data", "proxima_data"}
            ):
                valor = formatar_data(valor)
            registro[nome.replace("_", " ").capitalize()] = valor
        registros.append(registro)
    quadro = pd.DataFrame(registros)

    def estilo_linha(linha):
        cor = None
        for coluna in ("Situacao", "Status"):
            if coluna in linha:
                cor = CORES_STATUS_TEXTO.get(
                    str(linha[coluna]).lstrip("● ").replace(" ", "_")
                )
        return [f"color: {cor}; font-weight: 600" if cor else "" for _ in linha]

    estilizado = quadro.style.apply(estilo_linha, axis=1)
    if "Placa" in quadro.columns:
        estilizado = estilizado.set_properties(
            subset=["Placa"],
            **{
                "background-color": "#1E2227",
                "color": "#FAFAF9",
                "font-family": "'IBM Plex Mono', monospace",
                "font-weight": "600",
                "letter-spacing": "0.03em",
            },
        )
    st.dataframe(estilizado, hide_index=True, use_container_width=True)


def tabela_html(cabecalhos, linhas):
    """Tabela somente leitura, hairline entre linhas, sem zebra — para abas sem
    ação por linha (Plano de manutenção, Histórico, Contratos...). Cada célula
    de `linhas` já vem pronta como HTML (use selo_situacao/chip_placa/mono)."""
    def celula(conteudo, tag):
        return f"<{tag}>{conteudo}</{tag}>"

    ths = "".join(celula(c, "th") for c in cabecalhos)
    if not linhas:
        corpo = (
            f'<tr><td colspan="{len(cabecalhos)}">'
            f'{estado_vazio("Nenhum registro encontrado.", compacto=True)}</td></tr>'
        )
    else:
        corpo = "".join(
            "<tr>" + "".join(celula(valor, "td") for valor in linha) + "</tr>"
            for linha in linhas
        )
    st.markdown(
        f"""
        <div class="tabela-leitura">
          <table>
            <thead><tr>{ths}</tr></thead>
            <tbody>{corpo}</tbody>
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
    return f'<div class="barra">{itens}</div>'


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
        f'<div class="barra" style="margin:.6rem 0 .5rem;">{barra}</div>{legenda}',
        unsafe_allow_html=True,
    )


def barra_proporcional(percentual, cor="#2F9E6E"):
    """Barra de 100px (6px de altura) para tabelas de Relatórios, em vez de gráfico
    de biblioteca. `percentual` de 0 a 100; `cor` é um dos hex de CORES_BORDA (ou grafite)."""
    largura = max(0, min(100, int(percentual)))
    segmento = _SEGMENTO_POR_HEX.get(cor, "seg-alugada")
    return f'<div class="barra barra--fina {segmento}"><i style="width:{largura}%"></i></div>'


def indicador_etapas(atual, rotulos):
    """Assistente (wizard): círculos numerados conectados por linha — só usado em Novo contrato."""
    itens = ""
    for i, rotulo in enumerate(rotulos, start=1):
        concluido = i <= atual
        cor_fundo = "var(--grafite)" if concluido else "transparent"
        cor_borda = "var(--texto)" if concluido else "var(--texto-3)"
        cor_texto = "#FAFAF9" if concluido else "var(--texto-3)"
        if i > 1:
            cor_linha = "var(--texto)" if i <= atual else "var(--texto-3)"
            itens += f'<div style="flex:1;height:2px;background:{cor_linha};margin-top:1.05rem;"></div>'
        itens += f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:.4rem;">
          <div class="mono" style="width:2.1rem;height:2.1rem;border-radius:50%;background:{cor_fundo};
                      border:2px solid {cor_borda};display:flex;align-items:center;justify-content:center;
                      color:{cor_texto};font-weight:600;">{i}</div>
          <span class="fs-legenda texto-2" style="white-space:nowrap;">{rotulo}</span>
        </div>
        """
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;margin:1rem 0 1.5rem;">{itens}</div>',
        unsafe_allow_html=True,
    )


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
    st.session_state["contratos_visao"] = "ficha"
    st.session_state["contratos_id_selecionado"] = contrato_id
    st.switch_page("pages/4_Contratos.py")


def abrir_ficha_cliente(cliente_id):
    """Abre a página de clientes com a ficha indicada já selecionada."""
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


def sucesso():
    st.session_state["mensagem_sucesso"] = "Alterações salvas."
    st.rerun()


def cabecalho(titulo, exibir_titulo=True):
    from src.auth import require_login
    from src.ui.tema import aplicar

    # O app.py já aplica tema e login; a página só refaz isso se for executada sozinha.
    if not st.session_state.get("shell_pronto"):
        aplicar()
        require_login()
    if exibir_titulo:
        st.title(titulo)
    if mensagem := st.session_state.pop("mensagem_sucesso", None):
        st.success(mensagem)
