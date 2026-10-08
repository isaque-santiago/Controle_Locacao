"""Regras puras da lista de documentos da frota no frontend web."""

import re
from datetime import date

from src.domain.documentos import situacao_documento
from src.domain.paginacao import calcular_pagina

TODOS = "todos"
SITUACOES_ORDEM = ("vencido", "a_vencer", "em_dia")
SITUACAO_ROTULO = {"vencido": "Vencido", "a_vencer": "A vencer", "em_dia": "Em dia"}
TOM_SITUACAO = {"vencido": "perigo", "a_vencer": "atencao", "em_dia": "ok"}
TIPOS_ROTULO = {
    "ipva": "IPVA",
    "licenciamento": "Licenciamento",
    "seguro": "Seguro",
    "vistoria_detran": "Vistoria Detran",
    "outro": "Outro",
}


def situacao_valida(valor: str | None) -> str:
    return valor if valor in SITUACOES_ORDEM else TODOS


def _data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def classificar(documento: dict, hoje: date, alerta_dias: int) -> dict:
    """Situação e rótulo de exibição: documento regularizado aparece como "Regularizado" e conta como em dia."""
    situacao = situacao_documento(_data(documento["vencimento"]), bool(documento["regularizado"]), hoje, alerta_dias)
    rotulo = "Regularizado" if documento["regularizado"] else SITUACAO_ROTULO[situacao]
    return {"situacao": situacao, "rotulo": rotulo}


def filtrar(itens: list[dict], situacao: str, busca: str) -> list[dict]:
    """`itens`: {"documento", "placa", "situacao"}. A busca olha a placa, com ou sem hífen."""
    termo = re.sub(r"[^a-z0-9]", "", (busca or "").casefold())
    return [
        item for item in itens
        if (situacao == TODOS or item["situacao"] == situacao)
        and termo in re.sub(r"[^a-z0-9]", "", (item.get("placa") or "").casefold())
    ]


def montar_pagina(itens, situacao, busca, pagina, por_pagina):
    """Itens da página (vencidos primeiro, depois a vencer e em dia; pendentes antes dos regularizados; por
    vencimento), recorte e contagem por situação (a contagem ignora filtro e busca)."""
    filtrados = sorted(
        filtrar(itens, situacao, busca),
        key=lambda i: (SITUACOES_ORDEM.index(i["situacao"]), bool(i["documento"]["regularizado"]), str(i["documento"]["vencimento"])),
    )
    recorte = calcular_pagina(len(filtrados), pagina, por_pagina)
    contagem = {TODOS: len(itens), **{s: sum(i["situacao"] == s for i in itens) for s in SITUACOES_ORDEM}}
    return filtrados[recorte.inicio:recorte.fim], recorte, contagem
