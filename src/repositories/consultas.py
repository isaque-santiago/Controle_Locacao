"""Leitura paginada (com cache curto) para evitar truncamento pelo limite do PostgREST.

As listas ficam em cache por usuário (o RLS depende da sessão) e por dia (as views de
cobrança calculam a situação pela data). Toda escrita nos repositórios deve usar o
decorador `invalida_cache`, para o app nunca exibir dados que ele mesmo acabou de alterar.
"""

from functools import wraps

import streamlit as st
from postgrest.exceptions import APIError

from src.db import get_client
from src.domain.erros import eh_repeticao_de_envio
from src.domain.valores import hoje_br

# Rede de segurança para alterações feitas fora deste app (outro aparelho, painel do Supabase).
_TTL_SEGUNDOS = 60


def _ler_todos(tabela, ordem, selecao, filtros):
    # `ordem` pode ser uma coluna ou uma tupla de colunas (views sem id). Com uma só
    # coluna, o id desempata para a paginação não repetir nem perder linhas.
    if isinstance(ordem, str):
        ordens = (ordem,) if ordem == "id" else (ordem, "id")
    else:
        ordens = tuple(ordem)
    registros = []
    inicio = 0
    while True:
        consulta = get_client().table(tabela).select(selecao)
        for coluna in ordens:
            consulta = consulta.order(coluna)
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
    ordem = ordem if isinstance(ordem, str) else tuple(ordem)
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


def _por_chave(tabela, chave_operacao):
    achados = get_client().table(tabela).select("*").eq("chave_operacao", chave_operacao).limit(1).execute().data
    return achados[0] if achados else None


def inserir_idempotente(tabela, dados, chave_operacao=None):
    """Insere uma linha; com `chave_operacao`, repetir o envio devolve a linha já gravada.

    Consulta a chave antes (gatilhos do banco, como a validação de saldo do pagamento, rodam antes
    do índice único e recusariam o reenvio com outra mensagem) e trata o 23505 do índice
    `uq_*_chave_operacao` para o caso de dois envios simultâneos."""
    tabela_api = get_client().table(tabela)
    if not chave_operacao:
        return tabela_api.insert(dados).execute().data[0]
    existente = _por_chave(tabela, chave_operacao)
    if existente:
        return existente
    try:
        return tabela_api.insert({**dados, "chave_operacao": chave_operacao}).execute().data[0]
    except APIError as erro:
        existente = _por_chave(tabela, chave_operacao) if eh_repeticao_de_envio(erro) else None
        if existente:
            return existente
        raise


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
