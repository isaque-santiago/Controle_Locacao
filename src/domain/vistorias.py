"""Checklist padrão de vistoria, comparação entrega x devolução e resumos."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

CHECKLIST_PADRAO = (
    "farol_dianteiro",
    "farol_traseiro",
    "pisca_alerta",
    "freio_dianteiro",
    "freio_traseiro",
    "pneu_dianteiro",
    "pneu_traseiro",
    "retrovisores",
    "buzina",
    "escapamento",
    "carenagem",
    "banco",
    "capacete",
    "chave_reserva",
    "documentos_do_veiculo",
)

# Rótulos dos itens padrão cujo nome de exibição difere da chave por acento/hífen.
_ROTULOS_PADRAO = {
    "pisca_alerta": "Pisca-alerta",
    "documentos_do_veiculo": "Documentos do veículo",
}

ESTADOS_ITEM = ("ok", "avaria", "ausente", "nao_aplicavel")
NIVEIS_COMBUSTIVEL = ("vazio", "1/4", "1/2", "3/4", "cheio")
_FUSO = ZoneInfo("America/Sao_Paulo")


def checklist_inicial() -> dict:
    """Checklist padrão com todos os itens 'ok', para pré-preencher a tela
    de vistoria (o dono ajusta o que estiver diferente)."""
    return {item: "ok" for item in CHECKLIST_PADRAO}


def comparar_checklists(checklist_entrega: dict, checklist_devolucao: dict) -> dict:
    """Itens cujo valor mudou entre a vistoria de entrega e a de devolução
    (inclui itens presentes em só um dos dois lados)."""
    checklist_entrega = checklist_entrega or {}
    checklist_devolucao = checklist_devolucao or {}
    todas_as_chaves = set(checklist_entrega) | set(checklist_devolucao)

    diferencas = {}
    for chave in todas_as_chaves:
        valor_entrega = checklist_entrega.get(chave)
        valor_devolucao = checklist_devolucao.get(chave)
        if valor_entrega != valor_devolucao:
            diferencas[chave] = {"entrega": valor_entrega, "devolucao": valor_devolucao}
    return diferencas


def rotulo_item(chave: str) -> str:
    """'freio_dianteiro' -> 'Freio dianteiro' (itens adicionais mantêm o nome digitado)."""
    if chave in _ROTULOS_PADRAO:
        return _ROTULOS_PADRAO[chave]
    texto = str(chave).replace("_", " ").strip()
    return texto[:1].upper() + texto[1:]


def itens_ordenados(checklist: dict) -> list:
    """Itens do checklist com o padrão primeiro (na ordem do padrão) e os
    adicionais depois, em ordem alfabética — ordem estável entre as duas vistorias."""
    checklist = checklist or {}
    padrao = [c for c in CHECKLIST_PADRAO if c in checklist]
    extras = sorted(c for c in checklist if c not in CHECKLIST_PADRAO)
    return [(chave, checklist[chave]) for chave in padrao + extras]


def itens_com_avaria(checklist: dict) -> list:
    return [chave for chave, estado in itens_ordenados(checklist) if estado == "avaria"]


def contar_avarias(vistoria: dict) -> int:
    """Itens marcados como avaria; se só há descrição textual, conta como 1."""
    vistoria = vistoria or {}
    quantidade = len(itens_com_avaria(vistoria.get("checklist")))
    if quantidade == 0 and (vistoria.get("avarias") or "").strip():
        return 1
    return quantidade


def resumo_avarias(vistoria: dict):
    """Texto de avarias para a lista: a descrição digitada ou, na falta dela,
    os itens marcados como avaria. None quando não há avaria."""
    vistoria = vistoria or {}
    descricao = (vistoria.get("avarias") or "").strip()
    if descricao:
        return descricao
    itens = itens_com_avaria(vistoria.get("checklist"))
    return ", ".join(rotulo_item(i) for i in itens) or None


def km_rodados(entrega, devolucao):
    """Km rodados entre as duas vistorias; None enquanto faltar alguma."""
    if not entrega or not devolucao:
        return None
    return devolucao["km"] - entrega["km"]


def filtrar_por_tipo(vistorias: list, tipo: str) -> list:
    """'todas' devolve tudo; caso contrário, só o tipo pedido (entrega/devolucao)."""
    if tipo == "todas":
        return list(vistorias)
    return [v for v in vistorias if v["tipo"] == tipo]


def tipos_faltantes(vistorias_do_contrato: list) -> list:
    """Tipos (entrega, devolucao) ainda não registrados no contrato."""
    feitos = {v["tipo"] for v in vistorias_do_contrato}
    return [t for t in ("entrega", "devolucao") if t not in feitos]


def instante_da_vistoria(dia: date, agora: datetime) -> datetime:
    """Momento gravado para a vistoria: agora, se o dia informado é hoje
    (fuso America/Sao_Paulo); caso contrário meio-dia do dia informado, para
    que a data não mude por conversão de fuso."""
    agora = agora.astimezone(_FUSO)
    if dia == agora.date():
        return agora
    return datetime.combine(dia, time(12, 0), tzinfo=_FUSO)
