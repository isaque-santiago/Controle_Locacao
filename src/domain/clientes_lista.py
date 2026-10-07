"""Regras puras da lista e da ficha de clientes do frontend web."""

import re

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


def montar_pagina(registros, status, busca, pagina, por_pagina):
    filtrados = filtrar(registros, status, busca)
    recorte = calcular_pagina(len(filtrados), pagina, por_pagina)
    contagem = {chave: sum(c.get("status") == chave for c in registros) for chave in STATUS_ORDEM}
    return filtrados[recorte.inicio:recorte.fim], recorte, contagem
