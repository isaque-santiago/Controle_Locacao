"""Listas interativas em cartões com estrutura explícita (Plano de melhorias, Etapa 4).

Cada registro é um cartão com identidade (título + selo), dados rotulados e um grupo de ações.
O significado de cada parte vem de classes (`.registro__id`, `.registro__campo`...) e de
chaves de container (`lista_<prefixo>`, `reg_<prefixo>_<id>`, `regacoes_<prefixo>_<id>`),
nunca da posição da coluna: trocar a ordem de um campo no Python não troca o rótulo.

Uso:
    with lista_registros("documentos", acoes=3):
        for doc in itens:
            with registro("documentos", doc["id"], titulo_html, [campo("Vencimento", html)], selo) as acoes:
                if botao_acao(acoes, "editar", f"editar_doc_{doc['id']}"):
                    ...

A aparência (grade, quebra em telas estreitas por container query, rótulos sempre visíveis
nas ações) fica em estilos.css.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from html import escape

import streamlit as st


@dataclass(frozen=True)
class Campo:
    """Dado rotulado de um registro. `valor` já vem em HTML (use mono/chip_placa/selo_situacao)."""

    rotulo: str
    valor: str
    largo: bool = False  # ocupa a linha inteira em telas estreitas (textos longos)


def campo(rotulo, valor, largo=False):
    return Campo(rotulo, valor, largo)


def html_identidade(titulo, selo=None, subtitulo=None):
    """HTML da identidade do registro: título (placa, nome...), subtítulo e selo de situação."""
    corpo = f'<div class="registro__titulo">{titulo}</div>'
    if subtitulo:
        corpo += f'<div class="registro__subtitulo">{subtitulo}</div>'
    if selo:
        corpo += f'<div class="registro__selo">{selo}</div>'
    return f'<div class="registro__id">{corpo}</div>'


def html_dados(campos):
    """HTML dos dados rotulados do registro, como lista de definições (`<dl>`)."""
    itens = "".join(
        f'<div class="registro__campo{" registro__campo--largo" if c.largo else ""}">'
        f'<dt class="registro__rotulo">{escape(c.rotulo)}</dt><dd class="registro__valor">{c.valor}</dd></div>'
        for c in campos
    )
    return f'<dl class="registro__dados">{itens}</dl>'


@contextmanager
def lista_registros(prefixo, acoes=0):
    """Cartão que agrupa os registros de uma lista (borda, fundo e container query).
    `acoes` é o maior nº de botões de um registro (1 a 3): reserva a coluna de ações no desktop
    para que os dados fiquem alinhados entre as linhas."""
    sufixo = f"__a{acoes}" if acoes else ""
    with st.container(key=f"lista_{prefixo}{sufixo}"):
        yield


@contextmanager
def registro(prefixo, identificador, titulo, campos, selo=None, subtitulo=None, acoes=True, estado=None):
    """Um registro da lista. Devolve o grupo de ações (container horizontal) ou `None`
    quando `acoes=False`; use-o como alvo de `botao_acao`. `estado` ("selecionado" ou
    "indisponivel") só muda a aparência do cartão (listas de escolha, como no assistente)."""
    sufixo = {"selecionado": "__sel", "indisponivel": "__off"}.get(estado, "")
    with st.container(key=f"reg_{prefixo}_{identificador}{sufixo}"):
        st.markdown(html_identidade(titulo, selo, subtitulo), unsafe_allow_html=True)
        if campos:
            st.markdown(html_dados(campos), unsafe_allow_html=True)
        if acoes:
            grupo = st.container(key=f"regacoes_{prefixo}_{identificador}", horizontal=True, gap="small")
            with grupo:
                yield grupo
        else:
            yield None
