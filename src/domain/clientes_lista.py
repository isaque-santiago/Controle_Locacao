"""Regras puras da lista e da ficha de clientes do frontend web."""

import re

from src.domain.ordenacao import ordenar
from src.domain.paginacao import calcular_pagina

TODOS = "todos"
STATUS_ORDEM = ("ativo", "bloqueado", "inativo")
STATUS_ROTULO = {"ativo": "Ativo", "bloqueado": "Bloqueado", "inativo": "Inativo"}
ABAS_FICHA = (("resumo", "Resumo"), ("contratos", "Contratos"), ("pagamentos", "Pagamentos"), ("portal", "Portal"))


def status_valido(valor: str | None) -> str:
    return valor if valor in (TODOS, *STATUS_ORDEM) else TODOS


def aba_valida(valor: str | None) -> str:
    return valor if valor in dict(ABAS_FICHA) else ABAS_FICHA[0][0]


def filtrar(registros: list[dict], status: str, busca: str) -> list[dict]:
    termo = (busca or "").strip().casefold()
    digitos = re.sub(r"\D", "", termo)
    return [
        cliente for cliente in registros
        if (status == TODOS or cliente.get("status") == status)
        and (
            not termo
            or termo in (cliente.get("nome") or "").casefold()
            or bool(digitos and digitos in re.sub(r"\D", "", cliente.get("cpf") or ""))
        )
    ]


# Coluna da tabela -> campo da URL (`?ordem=nome`, `?ordem=-nome` para decrescente)
COLUNAS_ORDENAVEIS = {"Cliente": "nome", "Situação": "situacao", "CPF": "cpf", "CNH": "cnh"}


def ordenar_clientes(registros, campo, decrescente):
    chaves = {
        "nome": lambda c: (c.get("nome") or "").casefold() or None,
        "situacao": lambda c: STATUS_ORDEM.index(c["status"]) if c.get("status") in STATUS_ORDEM else len(STATUS_ORDEM),
        "cpf": lambda c: re.sub(r"\D", "", c.get("cpf") or "") or None,
        "cnh": lambda c: str(c["cnh_validade"])[:10] if c.get("cnh_validade") else None,
    }
    return ordenar(registros, campo, decrescente, chaves)


def montar_pagina(registros, status, busca, pagina, por_pagina, campo=None, decrescente=False):
    filtrados = ordenar_clientes(filtrar(registros, status, busca), campo, decrescente)
    recorte = calcular_pagina(len(filtrados), pagina, por_pagina)
    contagem = {chave: sum(c.get("status") == chave for c in registros) for chave in STATUS_ORDEM}
    return filtrados[recorte.inicio:recorte.fim], recorte, contagem
