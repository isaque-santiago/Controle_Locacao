"""Grupo de WhatsApp de cada locatário (seção 20 do plano; decisão do dono em 17/11/2026). Funções puras.

Cada locatário tem um grupo próprio com ele, o dono e as duas pessoas do financeiro. As mensagens automáticas vão
**para o grupo**, nunca para o número individual, e só as de cobrança e recibo (os outros avisos ficam fora por enquanto).
Cliente sem grupo: a mensagem fica `ignorada`, com o motivo, e o dono vê no sistema."""

import re

# ID de grupo da Evolution/WhatsApp: "120363025246125486@g.us" (atual) ou "5511999998888-1600000000@g.us" (antigo).
_GRUPO = re.compile(r"^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$")

# Só estes assuntos vão ao grupo: lembretes de vencimento, atraso, inadimplência e recibo.
TIPOS_NO_GRUPO = frozenset({"lembrete_vespera", "lembrete_vencimento", "atraso", "inadimplencia", "recibo_pagamento"})


def normalizar_grupo(texto) -> str | None:
    """O ID do grupo no formato da Evolution, ou None se o texto não parece um ID de grupo."""
    limpo = re.sub(r"\s+", "", str(texto or "")).lower()
    return limpo if _GRUPO.match(limpo) else None


def eh_grupo(destino) -> bool:
    """True quando o destino de uma mensagem é um grupo (e não um número individual)."""
    return normalizar_grupo(destino) is not None


def somente_assuntos_do_grupo(avisos) -> list:
    """Filtra os avisos devidos: fica só o que vai ao grupo (cobranças e recibos)."""
    return [a for a in avisos if a.tipo in TIPOS_NO_GRUPO]
