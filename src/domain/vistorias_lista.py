"""Regras puras da lista e da comparação de vistorias do frontend web."""

import re

from src.domain.paginacao import calcular_pagina

TODAS = "todas"
TIPOS_ORDEM = ("entrega", "devolucao")
TIPO_ROTULO = {"entrega": "Entrega", "devolucao": "Devolução"}
# Estado do item do checklist: rótulo e tom do selo. O estado é sempre escrito, nunca só colorido.
ESTADO_ITEM = {
    "ok": ("OK", "ok"),
    "avaria": ("Avaria", "perigo"),
    "ausente": ("Ausente", "perigo"),
    "nao_aplicavel": ("N/A", "neutro"),
}


def tipo_valido(valor: str | None) -> str:
    return valor if valor in TIPOS_ORDEM else TODAS


def filtrar(itens: list[dict], tipo: str, busca: str) -> list[dict]:
    """`itens`: {"vistoria", "cliente_nome", "placa"}. A busca olha o nome do cliente e a placa."""
    termo = (busca or "").strip().casefold()
    placa_termo = re.sub(r"[^a-z0-9]", "", termo)
    return [
        item for item in itens
        if (tipo == TODAS or item["vistoria"].get("tipo") == tipo)
        and (
            not termo
            or termo in (item.get("cliente_nome") or "").casefold()
            or bool(placa_termo and placa_termo in re.sub(r"[^a-z0-9]", "", (item.get("placa") or "").casefold()))
        )
    ]


def montar_pagina(itens, tipo, busca, pagina, por_pagina):
    """Itens da página (mais recentes primeiro), recorte e contagem por tipo (a contagem ignora filtro e busca)."""
    filtrados = sorted(filtrar(itens, tipo, busca), key=lambda i: str(i["vistoria"]["data"]), reverse=True)
    recorte = calcular_pagina(len(filtrados), pagina, por_pagina)
    contagem = {TODAS: len(itens)}
    for chave in TIPOS_ORDEM:
        contagem[chave] = sum(i["vistoria"].get("tipo") == chave for i in itens)
    return filtrados[recorte.inicio:recorte.fim], recorte, contagem
