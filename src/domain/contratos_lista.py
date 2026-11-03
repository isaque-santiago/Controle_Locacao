"""Regras puras da lista e da ficha de contratos do frontend web."""

import re

from decimal import Decimal

from src.domain.ordenacao import ordenar
from src.domain.paginacao import calcular_pagina

TODOS = "todos"
PADRAO = "ativo"
STATUS_ORDEM = ("ativo", "encerrado", "cancelado")
STATUS_ROTULO = {"ativo": "Ativo", "encerrado": "Encerrado", "cancelado": "Cancelado"}
PERIODOS_ROTULO = {"diario": "Diário", "semanal": "Semanal", "quinzenal": "Quinzenal", "mensal": "Mensal"}
ABAS_FICHA = (("cobrancas", "Cobranças"), ("vistorias", "Vistorias"), ("manutencoes", "Manutenções"))


def status_valido(valor: str | None) -> str:
    """Sem filtro na URL a lista abre nos contratos ativos, como no Streamlit."""
    return valor if valor in (TODOS, *STATUS_ORDEM) else PADRAO


def aba_valida(valor: str | None) -> str:
    return valor if valor in dict(ABAS_FICHA) else ABAS_FICHA[0][0]


def filtrar(itens: list[dict], status: str, busca: str) -> list[dict]:
    """`itens`: {"contrato", "cliente_nome", "placa"}. A busca olha o nome do cliente e a placa."""
    termo = (busca or "").strip().casefold()
    placa_termo = re.sub(r"[^a-z0-9]", "", termo)
    return [
        item for item in itens
        if (status == TODOS or item["contrato"].get("status") == status)
        and (
            not termo
            or termo in (item.get("cliente_nome") or "").casefold()
            or bool(placa_termo and placa_termo in re.sub(r"[^a-z0-9]", "", (item.get("placa") or "").casefold()))
        )
    ]


# Coluna da tabela -> campo da URL (`?ordem=inicio`, `?ordem=-inicio` para decrescente)
COLUNAS_ORDENAVEIS = {"Cliente": "cliente", "Situação": "situacao", "Moto": "placa", "Início": "inicio", "Valor / período": "valor"}


def ordenar_contratos(itens, campo, decrescente):
    chaves = {
        "cliente": lambda i: (i.get("cliente_nome") or "").casefold() or None,
        "situacao": lambda i: STATUS_ORDEM.index(i["contrato"]["status"]) if i["contrato"].get("status") in STATUS_ORDEM else len(STATUS_ORDEM),
        "placa": lambda i: re.sub(r"[^a-z0-9]", "", (i.get("placa") or "").casefold()) or None,
        "inicio": lambda i: str(i["contrato"]["data_inicio"])[:10] if i["contrato"].get("data_inicio") else None,
        "valor": lambda i: Decimal(str(i["contrato"]["valor_periodo"])) if i["contrato"].get("valor_periodo") is not None else None,
    }
    return ordenar(itens, campo, decrescente, chaves)


def montar_pagina(itens, status, busca, pagina, por_pagina, campo=None, decrescente=False):
    """Itens da página, recorte e contagem por situação (a contagem ignora filtro e busca).

    Sem `campo`, do início mais recente para o mais antigo; com `campo`, essa ordem desempata."""
    filtrados = sorted(filtrar(itens, status, busca), key=lambda i: i["contrato"]["data_inicio"], reverse=True)
    filtrados = ordenar_contratos(filtrados, campo, decrescente)
    recorte = calcular_pagina(len(filtrados), pagina, por_pagina)
    contagem = {chave: sum(i["contrato"].get("status") == chave for i in itens) for chave in STATUS_ORDEM}
    return filtrados[recorte.inicio:recorte.fim], recorte, contagem


def prazo_texto(data_fim_prevista) -> str | None:
    """None quando o contrato tem prazo indeterminado (a regra padrão da operação)."""
    return str(data_fim_prevista)[:10] if data_fim_prevista else None


def filtrar_motos(motos: list[dict], busca: str) -> list[dict]:
    """Motos do assistente: a busca olha a placa (com ou sem hífen) e "marca modelo"."""
    termo = (busca or "").strip().casefold()
    placa_termo = re.sub(r"[^a-z0-9]", "", termo)
    return [
        m for m in motos
        if not termo
        or termo in f"{m.get('marca', '')} {m.get('modelo', '')}".casefold()
        or bool(placa_termo and placa_termo in re.sub(r"[^a-z0-9]", "", (m.get("placa") or "").casefold()))
    ]
