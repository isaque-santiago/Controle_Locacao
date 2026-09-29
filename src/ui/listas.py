"""Filtros, busca, paginação e abas das listas (Plano de melhorias, Etapa 3).

Estratégia única para todas as páginas:
- o estado (filtro, busca, itens por página, página e aba) vive em `st.session_state` e
  sobrevive à ida a uma ficha e à volta (`persist_state="session"` nos widgets); a página
  volta a 1 quando o filtro, a busca ou o tamanho da página mudam;
- a busca só é aplicada com Enter ou ao sair do campo (comportamento do `st.text_input`),
  nunca a cada tecla;
- os filtros são pílulas nativas (`st.pills`) que quebram de linha em telas estreitas, sem
  perder o texto nem o alvo de toque de 44 px; o selecionado leva um marcador de "check";
- abas são `st.tabs` nativas com estado, que lembram a aba ativa e só executam o conteúdo dela.

Toda aparência vem de estilos.css (classes `.st-key-<prefixo>_...`); aqui só se monta a
estrutura. A aritmética de página fica em src/domain/paginacao.py.
"""

from dataclasses import dataclass
from html import escape
from typing import Any

import streamlit as st

from src.domain.paginacao import OPCOES_POR_PAGINA, Pagina, calcular_pagina, filtros_ativos


def _plural(quantidade, singular, plural):
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _chave_pagina(prefixo):
    return f"{prefixo}_pagina"


def _voltar_para_primeira(prefixo):
    st.session_state[_chave_pagina(prefixo)] = 1


def _limpar(prefixo, padrao):
    """Uma única ação devolve a lista ao estado inicial: filtro padrão, sem busca, página 1."""
    st.session_state[f"{prefixo}_filtro"] = padrao
    st.session_state[f"{prefixo}_busca"] = ""
    _voltar_para_primeira(prefixo)


# ------------------------------------------------------------------ filtros --


@dataclass
class FiltrosLista:
    """Estado lido da barra: `valor` (filtro escolhido) e `busca` (texto, sem espaços nas
    pontas). `resumo()` mostra o total de resultados, os filtros ativos e `Limpar filtros`."""

    prefixo: str
    valor: Any
    busca: str
    padrao: Any
    grupo: str
    rotulos: dict
    _resumo: Any

    def resumo(self, encontrados, unidade=("resultado", "resultados")):
        """Chame depois de filtrar: informa quantos registros restaram e o que está filtrado."""
        ativos = filtros_ativos(self.valor, self.padrao, self.busca)
        chips = ""
        if "filtro" in ativos:
            chips += f'<span class="filtro-ativo">{escape(self.grupo)}: {escape(str(self.rotulos[self.valor]))}</span>'
        if "busca" in ativos:
            chips += f'<span class="filtro-ativo">Busca: “{escape(self.busca)}”</span>'
        texto = f'<strong>{_plural(encontrados, *unidade)}</strong>'
        with self._resumo:
            with st.container(key=f"{self.prefixo}_resumo_filtros", horizontal=True, vertical_alignment="center"):
                st.markdown(
                    f'<div class="filtros-resumo" role="status">{texto}{chips}</div>',
                    unsafe_allow_html=True,
                )
                if ativos:
                    st.button(
                        "Limpar filtros",
                        key=f"{self.prefixo}_limpar",
                        icon=":material/filter_alt_off:",
                        type="tertiary",
                        help="Remove a busca e volta ao filtro inicial",
                        on_click=_limpar,
                        args=(self.prefixo, self.padrao),
                    )


def barra_filtros(prefixo, opcoes, padrao, contagens=None, grupo="Situação", busca=None):
    """Barra de filtros da lista: pílulas de uma escolha + campo de busca opcional.

    `opcoes` é uma lista de `(valor, rótulo)`; `contagens` (valor -> quantidade) acrescenta
    ` · n` ao rótulo; `busca` é o texto de exemplo do campo (sem ele, não há busca). Devolve
    `FiltrosLista`; depois de filtrar, chame `.resumo(len(filtrados))`."""
    rotulos = dict(opcoes)

    def rotulo(valor):
        if contagens is None or valor not in contagens:
            return rotulos[valor]
        return f"{rotulos[valor]} · {contagens[valor]}"

    with st.container(key=f"{prefixo}_barra_filtros", horizontal=True, vertical_alignment="center"):
        valor = st.pills(
            grupo,
            list(rotulos),
            default=padrao,
            required=True,
            format_func=rotulo,
            key=f"{prefixo}_filtro",
            persist_state="session",
            on_change=_voltar_para_primeira,
            args=(prefixo,),
            label_visibility="collapsed",
        )
        texto = ""
        if busca:
            texto = st.text_input(
                "Buscar",
                placeholder=busca,
                icon=":material/search:",
                key=f"{prefixo}_busca",
                persist_state="session",
                on_change=_voltar_para_primeira,
                args=(prefixo,),
                label_visibility="collapsed",
            ).strip()
    return FiltrosLista(prefixo, valor, texto, padrao, grupo, rotulos, st.container())


# ---------------------------------------------------------------- paginação --


def paginar(prefixo, registros):
    """Recorta `registros` na página atual da lista `prefixo`. Devolve `(itens, Pagina)`;
    mostre o rodapé com `rodape_paginacao(prefixo, pagina)` depois da lista."""
    por_pagina = st.session_state.get(f"{prefixo}_por_pagina", OPCOES_POR_PAGINA[0])
    pagina = calcular_pagina(len(registros), st.session_state.get(_chave_pagina(prefixo), 1), por_pagina)
    st.session_state[_chave_pagina(prefixo)] = pagina.pagina  # a lista pode ter encolhido
    return registros[pagina.inicio : pagina.fim], pagina


def _mudar_pagina(prefixo, destino):
    st.session_state[_chave_pagina(prefixo)] = destino


def rodape_paginacao(prefixo, pagina: Pagina):
    """`Anterior`, informação da página, `Próxima` e itens por página. Some enquanto tudo
    cabe na menor página (não há o que paginar nem o que escolher)."""
    if pagina.total <= OPCOES_POR_PAGINA[0]:
        return
    with st.container(key=f"{prefixo}_paginacao", horizontal=True, vertical_alignment="center"):
        st.markdown(f'<div class="paginacao__info" role="status">{pagina.resumo()}</div>', unsafe_allow_html=True)
        st.button(
            "Anterior",
            key=f"{prefixo}_anterior",
            icon=":material/chevron_left:",
            disabled=not pagina.tem_anterior,
            on_click=_mudar_pagina,
            args=(prefixo, pagina.pagina - 1),
        )
        st.button(
            "Próxima",
            key=f"{prefixo}_proxima",
            icon=":material/chevron_right:",
            icon_position="right",
            disabled=not pagina.tem_proxima,
            on_click=_mudar_pagina,
            args=(prefixo, pagina.pagina + 1),
        )
        st.selectbox(
            "Itens por página",
            OPCOES_POR_PAGINA,
            key=f"{prefixo}_por_pagina",
            persist_state="session",
            format_func=lambda n: f"{n} por página",
            on_change=_voltar_para_primeira,
            args=(prefixo,),
            label_visibility="collapsed",
        )


# --------------------------------------------------------------------- abas --


def _lembrar_aba(chave, rotulos):
    atual = st.session_state.get(chave)
    if atual in rotulos:
        st.session_state[f"{chave}_indice"] = list(rotulos).index(atual)


def abas(chave, rotulos):
    """Abas nativas que lembram a aba ativa entre execuções (inclusive quando o rótulo muda,
    como ` · 3` de contagem, e na volta de outra página). Devolve os contêineres; desenhe o
    conteúdo só onde `aba_ativa(guia)` for verdadeiro, para não executar as abas ocultas."""
    rotulos = list(rotulos)
    indice = min(st.session_state.get(f"{chave}_indice", 0), len(rotulos) - 1)
    return st.tabs(
        rotulos,
        key=chave,
        default=rotulos[indice],
        on_change=_lembrar_aba,
        args=(chave, rotulos),
    )


def aba_ativa(guia):
    """Verdadeiro se a aba está selecionada (ou se o estado não é rastreado)."""
    return guia.open is not False


def reiniciar_abas(chave):
    """Esquece a aba lembrada — para quando o contexto muda (ex.: outra ficha)."""
    st.session_state.pop(f"{chave}_indice", None)
