"""Leitura paginada (com cache curto) para evitar truncamento pelo limite do PostgREST.

As listas ficam em cache por usuário (o RLS depende da sessão) e por dia (as views de
cobrança calculam a situação pela data). Toda escrita nos repositórios deve usar o
decorador `invalida_cache`, para o app nunca exibir dados que ele mesmo acabou de alterar.
"""

from functools import wraps

import streamlit as st

from src.db import get_client
from src.domain.valores import hoje_br

# Rede de segurança para alterações feitas fora deste app (outro aparelho, painel do Supabase).
_TTL_SEGUNDOS = 60


def _ler_todos(tabela, ordem, selecao, filtros):
    registros = []
    inicio = 0
    while True:
        consulta = get_client().table(tabela).select(selecao).order(ordem)
        if ordem != "id":
            consulta = consulta.order("id")
        for campo, valor in filtros:
            consulta = consulta.eq(campo, valor)
        pagina = consulta.range(inicio, inicio + 499).execute().data
        registros.extend(pagina)
        if not pagina:
            return registros
        inicio += len(pagina)


@st.cache_data(ttl=_TTL_SEGUNDOS, show_spinner=False)
def _todos_em_cache(usuario_id, dia, tabela, ordem, selecao, filtros):
    return _ler_todos(tabela, ordem, selecao, filtros)


def todos(tabela, ordem="id", selecao="*", filtros=None, usar_cache=True):
    filtros_ordenados = tuple(sorted((filtros or {}).items()))
    if not usar_cache:
        return _ler_todos(tabela, ordem, selecao, filtros_ordenados)
    usuario = st.session_state.get("usuario") or {}
    return _todos_em_cache(
        usuario.get("id"),
        hoje_br().isoformat(),
        tabela,
        ordem,
        selecao,
        filtros_ordenados,
    )


def limpar_cache() -> None:
    _todos_em_cache.clear()


def invalida_cache(funcao):
    """Marca uma função de escrita: ao terminar (mesmo com erro), descarta o cache."""

    @wraps(funcao)
    def envoltorio(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        finally:
            limpar_cache()

    return envoltorio
