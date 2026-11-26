"""Grupo de WhatsApp de cada locatário (seção 20 do plano; decisão do dono em 17/11/2026). Funções puras.

Cada locatário tem um grupo próprio com ele, o dono e as duas pessoas do financeiro. As mensagens automáticas vão
**para o grupo**, nunca para o número individual. Desde 26/11/2026 vão todos os avisos (antes, só cobranças e recibos).
Cliente sem grupo: a mensagem fica `ignorada`, com o motivo, e o dono vê no sistema."""

import re

# ID de grupo da Evolution/WhatsApp: "120363025246125486@g.us" (atual) ou "5511999998888-1600000000@g.us" (antigo).
_GRUPO = re.compile(r"^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$")

# Cobranças e recibos: abrem a mensagem e entram sempre todos (o total precisa bater com as linhas).
TIPOS_DE_COBRANCA = frozenset({"lembrete_vespera", "lembrete_vencimento", "atraso", "inadimplencia", "recibo_pagamento"})

# Tudo o que vai ao grupo. A lista é explícita: um tipo de aviso novo só sai depois de o dono decidir.
TIPOS_NO_GRUPO = TIPOS_DE_COBRANCA | frozenset({
    "cnh_proxima", "cnh_vencida", "oleo_proxima", "oleo_vencida",
    "documento_proximo", "documento_vencido", "portal_acesso", "portal_senha_alterada",
})


def normalizar_grupo(texto) -> str | None:
    """O ID do grupo no formato da Evolution, ou None se o texto não parece um ID de grupo."""
    limpo = re.sub(r"\s+", "", str(texto or "")).lower()
    return limpo if _GRUPO.match(limpo) else None


def eh_grupo(destino) -> bool:
    """True quando o destino de uma mensagem é um grupo (e não um número individual)."""
    return normalizar_grupo(destino) is not None


def somente_assuntos_do_grupo(avisos) -> list:
    """Filtra os avisos devidos: fica só o que está liberado para ir ao grupo."""
    return [a for a in avisos if a.tipo in TIPOS_NO_GRUPO]


def opcoes_de_grupos(grupos, atual: str | None = None) -> list[tuple[str, str]]:
    """Opções da lista suspensa do cadastro: `(id, "Nome (N participantes)")`. Se o grupo atual do cliente não está na lista
    (ainda não atualizada), ele entra mesmo assim, para salvar o formulário sem querer não o remover."""
    opcoes = []
    for g in grupos:
        tamanho = g.get("participantes")
        opcoes.append((g["id"], f"{g['nome']} ({tamanho} participantes)" if tamanho else g["nome"]))
    if atual and atual not in {id_ for id_, _ in opcoes}:
        opcoes.append((atual, "Grupo atual (fora da lista)"))
    return sorted(opcoes, key=lambda o: o[1].lower())
