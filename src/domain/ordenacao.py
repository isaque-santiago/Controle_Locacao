"""Ordenação de listas por coluna: regras puras (sem Streamlit nem FastAPI).

O parâmetro `ordem` da URL é o nome do campo (crescente) ou `-campo` (decrescente); vazio mantém a ordem padrão da lista."""

from collections.abc import Callable, Iterable

ESTADO_CRESCENTE = "ascending"
ESTADO_DECRESCENTE = "descending"
ESTADO_NENHUM = "none"


def interpretar(valor: str | None, permitidas: Iterable[str]) -> tuple[str | None, bool]:
    """(campo, decrescente). Campo desconhecido ou vazio vira (None, False): ordem padrão."""
    texto = (valor or "").strip()
    decrescente = texto.startswith("-")
    campo = texto[1:] if decrescente else texto
    return (campo, decrescente) if campo in set(permitidas) else (None, False)


def valor_da_url(campo: str | None, decrescente: bool) -> str:
    return "" if not campo else ("-" + campo if decrescente else campo)


def proxima(campo_atual: str | None, decrescente: bool, campo: str) -> str:
    """Valor de `ordem` ao clicar na coluna `campo`: crescente, depois decrescente, depois volta ao padrão."""
    if campo_atual != campo:
        return campo
    return "" if decrescente else "-" + campo


def ordenar(itens: list, campo: str | None, decrescente: bool, chaves: dict[str, Callable]) -> list:
    """Ordena por `chaves[campo]`; itens sem valor (None) ficam sempre no fim. Estável: empates mantêm a ordem anterior."""
    if not campo:
        return list(itens)
    chave = chaves[campo]
    com_valor = [i for i in itens if chave(i) is not None]
    sem_valor = [i for i in itens if chave(i) is None]
    com_valor.sort(key=chave, reverse=decrescente)
    return com_valor + sem_valor


def cabecalhos(colunas: dict[str, str], campo_atual: str | None, decrescente: bool, url_da_ordem: Callable[[str], str]) -> dict[str, dict]:
    """Por rótulo de coluna: o endereço do próximo clique e o estado (`aria-sort`). `colunas` mapeia rótulo -> campo."""
    resultado = {}
    for rotulo, campo in colunas.items():
        if campo != campo_atual:
            estado = ESTADO_NENHUM
        else:
            estado = ESTADO_DECRESCENTE if decrescente else ESTADO_CRESCENTE
        resultado[rotulo] = {"campo": campo, "url": url_da_ordem(proxima(campo_atual, decrescente, campo)), "estado": estado}
    return resultado
