"""Leitura paginada para evitar truncamento pelo limite do PostgREST."""

from src.db import get_client


def todos(tabela, ordem="id", selecao="*", filtros=None):
    registros = []
    inicio = 0
    while True:
        consulta = get_client().table(tabela).select(selecao).order(ordem)
        if ordem != "id":
            consulta = consulta.order("id")
        for campo, valor in (filtros or {}).items():
            consulta = consulta.eq(campo, valor)
        pagina = consulta.range(inicio, inicio + 499).execute().data
        registros.extend(pagina)
        if not pagina:
            return registros
        inicio += len(pagina)
