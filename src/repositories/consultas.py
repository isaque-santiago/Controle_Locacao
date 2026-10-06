"""Leitura paginada (com cache curto) para evitar truncamento pelo limite do PostgREST.

As listas ficam em cache por usuário (o RLS depende da sessão) e por dia (as views de
cobrança calculam a situação pela data). Toda escrita nos repositórios deve usar o
decorador `invalida_cache`, para o app nunca exibir dados que ele mesmo acabou de alterar.
"""

from copy import deepcopy
from functools import wraps
from threading import Lock
from time import monotonic

from postgrest.exceptions import APIError

from src.db import get_client, usuario_id_atual
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


# Cache próprio (funciona no Streamlit e no FastAPI). A chave sempre inclui o usuário; sem
# usuário identificado não há cache, para nunca servir dados de um usuário a outro.
_CACHE: dict[tuple, tuple[float, list]] = {}
_TRAVA_CACHE = Lock()


def _todos_em_cache(usuario_id, dia, tabela, ordem, selecao, filtros):
    chave = (usuario_id, dia, tabela, ordem, selecao, filtros)
    agora = monotonic()
    with _TRAVA_CACHE:
        achado = _CACHE.get(chave)
        if achado and achado[0] > agora:
            return deepcopy(achado[1])
    registros = _ler_todos(tabela, ordem, selecao, filtros)
    with _TRAVA_CACHE:
        for velha in [c for c, (validade, _) in _CACHE.items() if validade <= agora]:
            del _CACHE[velha]
        _CACHE[chave] = (agora + _TTL_SEGUNDOS, deepcopy(registros))
    return registros


def todos(tabela, ordem="id", selecao="*", filtros=None, usar_cache=True):
    ordem = ordem if isinstance(ordem, str) else tuple(ordem)
    filtros_ordenados = tuple(sorted((filtros or {}).items()))
    usuario_id = usuario_id_atual()
    if not usar_cache or not usuario_id:
        return _ler_todos(tabela, ordem, selecao, filtros_ordenados)
    return _todos_em_cache(
        usuario_id,
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
    with _TRAVA_CACHE:
        _CACHE.clear()


def invalida_cache(funcao):
    """Marca uma função de escrita: ao terminar (mesmo com erro), descarta o cache."""

    @wraps(funcao)
    def envoltorio(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        finally:
            limpar_cache()

    return envoltorio
