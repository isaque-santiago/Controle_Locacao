"""Regras de exibição do envio de WhatsApp para o dono: lista de mensagens, filtros e alertas do Dashboard (seção 20).

Uma mensagem é um dicionário simples: `id, cliente_id, cliente (nome), numero, texto, status, tentativas, erro,
enviar_apos, enviada_em, criado_em, tipos (lista dos assuntos)`. Datas podem vir como texto ISO."""

from datetime import datetime, timedelta

from src.domain.painel import TOM_ATENCAO, TOM_PERIGO, ItemAlerta

STATUS_ROTULO = {
    "pendente": "Aguardando envio", "enviada": "Enviada", "falhou": "Falhou",
    "ignorada": "Não enviada", "cancelada": "Cancelada",
}
STATUS_TOM = {"pendente": "atencao", "enviada": "ok", "falhou": "perigo", "ignorada": "atencao", "cancelada": "neutro"}

TIPO_ROTULO = {
    "lembrete_vespera": "Parcela perto de vencer", "lembrete_vencimento": "Parcela vence hoje",
    "atraso": "Pagamento em atraso", "inadimplencia": "Atraso prolongado", "recibo_pagamento": "Pagamento recebido",
    "cnh_proxima": "CNH perto de vencer", "cnh_vencida": "CNH vencida",
    "oleo_proxima": "Troca de óleo próxima", "oleo_vencida": "Troca de óleo atrasada",
    "documento_proximo": "Documento perto de vencer", "documento_vencido": "Documento vencido",
    "portal_acesso": "Acesso ao portal", "portal_senha_alterada": "Senha do portal alterada",
}

FILTROS = (("problemas", "Com problema"), ("pendentes", "Aguardando"), ("enviadas", "Enviadas"), ("todas", "Todas"))
_STATUS_DO_FILTRO = {"problemas": ("falhou", "ignorada"), "pendentes": ("pendente",), "enviadas": ("enviada",)}

DIAS_DE_PROBLEMA = 7             # só conta problema recente no alerta
RODADA_PARADA_MINUTOS = 90       # a tarefa roda a cada 20 min; depois de 90 sem rodar, algo parou


def filtro_valido(valor: str | None) -> str:
    return valor if valor in dict(FILTROS) else FILTROS[0][0]


def filtrar(mensagens: list[dict], filtro: str) -> list[dict]:
    status = _STATUS_DO_FILTRO.get(filtro)
    return [m for m in mensagens if status is None or m["status"] in status]


def contar_por_filtro(mensagens: list[dict]) -> dict[str, int]:
    return {chave: len(filtrar(mensagens, chave)) for chave, _ in FILTROS}


def assuntos(mensagem: dict) -> list[str]:
    return [TIPO_ROTULO.get(t, t) for t in mensagem.get("tipos") or []]


def pode_cancelar(mensagem: dict) -> bool:
    return mensagem["status"] in ("pendente", "falhou")


def pode_reenviar(mensagem: dict) -> bool:
    """Só o que falhou depois de tentar: sem número válido (`ignorada`) o reenvio não adiantaria."""
    return mensagem["status"] == "falhou" and bool(mensagem.get("numero"))


def _data(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor
    if not valor:
        return None
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))


def clientes_com_problema(mensagens: list[dict], agora: datetime, dias: int = DIAS_DE_PROBLEMA) -> list[dict]:
    """Clientes cuja mensagem mais recente (nos últimos `dias`) falhou ou não pôde ser enviada.
    Quando uma mensagem posterior chega, o problema some: o alerta acompanha a situação de hoje."""
    limite = agora - timedelta(days=dias)
    ultima: dict[str, dict] = {}
    for m in mensagens:
        criada = _data(m.get("criado_em"))
        if criada is None or criada < limite or m["status"] == "cancelada":
            continue
        atual = ultima.get(m["cliente_id"])
        if atual is None or criada > _data(atual["criado_em"]):
            ultima[m["cliente_id"]] = m
    return sorted(
        (m for m in ultima.values() if m["status"] in ("falhou", "ignorada")),
        key=lambda m: (m["status"] != "falhou", m.get("cliente") or ""),
    )


def alertas_whatsapp(config: dict, mensagens: list[dict], agora: datetime) -> list[ItemAlerta]:
    """Itens do cartão "Precisa de atenção" ligados ao envio. Sem o envio ligado, nenhum alerta."""
    if not config.get("whatsapp_ativo"):
        return []
    itens: list[ItemAlerta] = []

    ultima = _data(config.get("whatsapp_ultima_rodada_em"))
    if ultima is None or agora - ultima > timedelta(minutes=RODADA_PARADA_MINUTOS):
        quando = "ainda não rodou" if ultima is None else "não roda há mais de 1h30"
        itens.append(ItemAlerta(1, "Envio automático parado", f"A tarefa agendada {quando}. Veja o log no Coolify.", TOM_PERIGO, "mensagens"))
    else:
        estado = config.get("whatsapp_ultimo_estado")
        if estado == "indisponivel":
            itens.append(ItemAlerta(1, "Evolution fora do ar", "As mensagens ficam na fila e voltam a sair quando ela responder.", TOM_PERIGO, "mensagens"))
        elif estado and estado != "open":
            itens.append(ItemAlerta(1, "WhatsApp desconectado", "Leia o QR code da instância na Evolution para voltar a enviar.", TOM_PERIGO, "mensagens"))

    if config.get("whatsapp_modo_teste", True):
        itens.append(ItemAlerta(1, "WhatsApp em modo teste", "As mensagens vão só para o número de teste, não para os clientes.", TOM_ATENCAO, "configuracoes"))

    problemas = clientes_com_problema(mensagens, agora)
    if problemas:
        primeiro = problemas[0]
        resto = f" e mais {len(problemas) - 1}" if len(problemas) > 1 else ""
        motivo = primeiro.get("erro") or STATUS_ROTULO[primeiro["status"]]
        tom = TOM_PERIGO if primeiro["status"] == "falhou" else TOM_ATENCAO
        itens.append(ItemAlerta(len(problemas), "Mensagens sem entrega", f"{primeiro.get('cliente') or 'Cliente'}: {motivo}{resto}", tom, "mensagens"))
    return itens


def achatar(registro: dict) -> dict:
    """Mensagem como vem do banco (com `clientes` e `mensagens_whatsapp_itens` embutidos) no formato desta página."""
    base = {k: v for k, v in registro.items() if k not in ("clientes", "mensagens_whatsapp_itens")}
    cliente = registro.get("clientes") or {}
    base["cliente"] = cliente.get("nome") if isinstance(cliente, dict) else None
    base["tipos"] = [i["tipo"] for i in registro.get("mensagens_whatsapp_itens") or []]
    return base


def estado_da_instancia(estado: str | None) -> str:
    """Texto do estado da instância gravado pela última rodada, para a tela de Configurações."""
    if not estado:
        return "ainda sem rodada"
    return {
        "open": "conectada", "close": "desconectada (leia o QR code na Evolution)",
        "indisponivel": "Evolution fora do ar", "connecting": "conectando",
    }.get(estado, estado)
