"""Quais avisos de WhatsApp são devidos num dia de envio (seção 20 do plano). Funções puras.

Tudo é calculado para o `dia_envio`: o dia em que a mensagem de fato sai (o próprio dia, se estiver na janela de
`janela_envio`, ou o próximo dia de envio). Assim um aviso que cairia num domingo ou feriado não se perde: vai
para o dia de envio seguinte, com os números (dias de atraso, encargos) desse dia. O `data_referencia` do aviso
é sempre o `dia_envio`, e com ele a chave única do banco barra o mesmo aviso duas vezes.

Entradas são dicionários simples (o que as RPCs de leitura devolverão na Etapa 3); a saída é uma lista de `Aviso`.

`historico` diz o que já foi enfileirado: `{(tipo, referencia_id): [datas]}`, sem contar o que ficou `ignorada` ou
`cancelada`. Os avisos que se repetem seguem a escala do dono: 1º aviso, depois +2 dias (o "dia 3"), +6 ("dia 7") e a
cada 3 dias, até `max_repeticoes` avisos por assunto.
"""

from collections import namedtuple
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from src.domain.encargos import calcular_encargos
from src.domain.janela_envio import dia_de_envio_anterior

Aviso = namedtuple("Aviso", "tipo cliente_id referencia_id data_referencia dados")

TIPOS = (
    "lembrete_vespera", "lembrete_vencimento", "atraso", "inadimplencia", "recibo_pagamento",
    "cnh_proxima", "cnh_vencida", "oleo_proxima", "oleo_vencida",
    "documento_proximo", "documento_vencido", "portal_acesso", "portal_senha_alterada",
)

_SEM_ENCARGOS = Decimal("0.00")


@dataclass(frozen=True)
class ConfigAvisos:
    max_repeticoes: int = 10          # máximo de avisos por assunto que se repete
    dias_inadimplencia: int = 15      # corte das Configurações
    reenvio_proximo_dias: int = 30    # aviso "próxima" não se repete antes disso
    evento_recente_dias: int = 2      # recibo e portal: só o que aconteceu até N dias atrás (não enfileira o passado)
    multa_atraso: Decimal = Decimal("0.00")
    encargo_diario: Decimal = Decimal("0.00")


# ------------------------------------------------------------------ escala --

_DEGRAUS = (0, 2, 6)  # dias depois do 1º aviso: 1º, 3º e 7º dia de atraso
_INTERVALO = 3        # depois do 7º dia, a cada 3 dias


def _previstos_ate(dias_desde_o_primeiro: int) -> int:
    """Quantos avisos a escala já previa até `dias_desde_o_primeiro` depois do primeiro."""
    previstos = sum(1 for degrau in _DEGRAUS if degrau <= dias_desde_o_primeiro)
    if dias_desde_o_primeiro > _DEGRAUS[-1]:
        previstos += (dias_desde_o_primeiro - _DEGRAUS[-1]) // _INTERVALO
    return previstos


def escala_devida(dia: date, datas_enviadas, maximo: int = 10) -> bool:
    """Já é hora do próximo aviso da escala? Sem aviso anterior, sim.

    Se um dia foi perdido, o aviso atrasado sai no próximo dia possível, mas nunca com menos de 2 dias do anterior,
    e nunca mais de um por dia.
    """
    datas = sorted(datas_enviadas or ())
    if not datas:
        return maximo > 0
    if len(datas) >= maximo or datas[-1] >= dia or (dia - datas[-1]).days < 2:
        return False
    return len(datas) < _previstos_ate((dia - datas[0]).days)


def _sem_aviso(historico, tipo, referencia_id, desde=None, janela_dias=None, dia=None) -> bool:
    """Nunca avisado (ou, com `janela_dias`, não avisado nos últimos N dias). `desde` ignora o que veio antes."""
    datas = _datas(historico, tipo, referencia_id, desde)
    if janela_dias is not None:
        return not any(d > dia - timedelta(days=janela_dias) for d in datas)
    return not datas


def _datas(historico, tipo, referencia_id, desde=None) -> list:
    datas = (historico or {}).get((tipo, str(referencia_id)), ())
    return [d for d in datas if desde is None or d >= desde]


def _aviso(tipo, cliente_id, referencia_id, dia, **dados) -> Aviso:
    return Aviso(tipo, str(cliente_id), str(referencia_id), dia, dados)


# ---------------------------------------------------------------- cobranças --


def avisos_de_cobrancas(dia_envio: date, cobrancas, historico, cfg: ConfigAvisos) -> list[Aviso]:
    """Lembretes, atraso e corte de inadimplência.

    Cada cobrança: `id, cliente_id, tipo, vencimento, saldo, periodicidade, situacao, placa`.
    Só entram as abertas ou atrasadas com saldo. O lembrete de véspera sai no último dia de envio antes do
    vencimento (então um vencimento de segunda é lembrado no sábado) e não existe em contrato diário.
    """
    avisos = []
    for c in cobrancas:
        saldo = Decimal(str(c["saldo"]))
        if c["situacao"] not in ("aberta", "atrasada") or saldo <= 0:
            continue
        vencimento = c["vencimento"]
        base = dict(
            vencimento=vencimento, placa=c.get("placa"), saldo=saldo,
            tipo_cobranca=c.get("tipo", "locacao"), periodicidade=c.get("periodicidade"),
        )
        dias_atraso = (dia_envio - vencimento).days

        if dias_atraso < 0:
            if (
                c.get("periodicidade") != "diario"
                and dia_envio == dia_de_envio_anterior(vencimento)
                and _sem_aviso(historico, "lembrete_vespera", c["id"])
            ):
                avisos.append(_aviso("lembrete_vespera", c["cliente_id"], c["id"], dia_envio,
                                     **base, dias_ate_vencer=-dias_atraso))
        elif dias_atraso == 0:
            if _sem_aviso(historico, "lembrete_vencimento", c["id"]):
                avisos.append(_aviso("lembrete_vencimento", c["cliente_id"], c["id"], dia_envio, **base))
        else:
            encargos = calcular_encargos(
                c.get("tipo", "locacao"), saldo, vencimento, dia_envio, cfg.multa_atraso, cfg.encargo_diario)
            atraso = dict(base, dias_atraso=dias_atraso, encargos=encargos["encargos"], total=encargos["total"])
            if escala_devida(dia_envio, _datas(historico, "atraso", c["id"]), cfg.max_repeticoes):
                avisos.append(_aviso("atraso", c["cliente_id"], c["id"], dia_envio, **atraso))
            if dias_atraso >= cfg.dias_inadimplencia and _sem_aviso(historico, "inadimplencia", c["id"]):
                avisos.append(_aviso("inadimplencia", c["cliente_id"], c["id"], dia_envio, **atraso))
    return avisos


def avisos_de_recibos(dia_envio: date, pagamentos, historico, cfg: ConfigAvisos) -> list[Aviso]:
    """Recibo de pagamento. Cada pagamento: `id, cliente_id, data_pagamento, valor, placa, vencimento, saldo_restante`.
    Só os recentes: ao ligar o envio, os pagamentos antigos não geram recibo."""
    limite = dia_envio - timedelta(days=cfg.evento_recente_dias)
    avisos = []
    for p in pagamentos:
        if p["data_pagamento"] >= limite and _sem_aviso(historico, "recibo_pagamento", p["id"]):
            avisos.append(_aviso(
                "recibo_pagamento", p["cliente_id"], p["id"], dia_envio,
                valor=Decimal(str(p["valor"])), placa=p.get("placa"), vencimento=p.get("vencimento"),
                saldo_restante=Decimal(str(p.get("saldo_restante") or 0)),
            ))
    return avisos


# ------------------------------------------------------------------- alertas --


def avisos_de_cnh(dia_envio: date, cnhs, historico, cfg: ConfigAvisos) -> list[Aviso]:
    """CNH do locatário com contrato ativo. Cada item: `cliente_id, cnh_validade, situacao` (`a_vencer` ou `vencida`).
    A escala da CNH vencida só conta os avisos desde a data de validade (uma renovação reinicia o ciclo)."""
    avisos = []
    for c in cnhs:
        validade = c["cnh_validade"]
        dados = dict(validade=validade, dias=(validade - dia_envio).days)
        if c["situacao"] == "a_vencer" and validade >= dia_envio:
            if _sem_aviso(historico, "cnh_proxima", c["cliente_id"], janela_dias=cfg.reenvio_proximo_dias, dia=dia_envio):
                avisos.append(_aviso("cnh_proxima", c["cliente_id"], c["cliente_id"], dia_envio, **dados))
        elif c["situacao"] == "vencida" and validade < dia_envio:
            if escala_devida(dia_envio, _datas(historico, "cnh_vencida", c["cliente_id"], validade), cfg.max_repeticoes):
                avisos.append(_aviso("cnh_vencida", c["cliente_id"], c["cliente_id"], dia_envio, **dados))
    return avisos


def avisos_de_documentos(dia_envio: date, documentos, historico, cfg: ConfigAvisos) -> list[Aviso]:
    """Documentos da moto, avisados ao locatário do contrato ativo. Cada item: `id, cliente_id, placa, tipo_documento,
    descricao, vencimento, situacao` (`a_vencer` ou `vencido`). Some quando o dono marca como regularizado
    (a view deixa de listá-lo)."""
    avisos = []
    for d in documentos:
        dados = dict(
            placa=d.get("placa"), tipo_documento=d["tipo_documento"], descricao=d.get("descricao"),
            vencimento=d["vencimento"], dias=(d["vencimento"] - dia_envio).days,
        )
        if d["situacao"] == "a_vencer" and d["vencimento"] >= dia_envio:
            if _sem_aviso(historico, "documento_proximo", d["id"], janela_dias=cfg.reenvio_proximo_dias, dia=dia_envio):
                avisos.append(_aviso("documento_proximo", d["cliente_id"], d["id"], dia_envio, **dados))
        elif d["situacao"] == "vencido" and d["vencimento"] < dia_envio:
            if escala_devida(dia_envio, _datas(historico, "documento_vencido", d["id"]), cfg.max_repeticoes):
                avisos.append(_aviso("documento_vencido", d["cliente_id"], d["id"], dia_envio, **dados))
    return avisos


def avisos_de_oleo(dia_envio: date, alertas, historico, cfg: ConfigAvisos) -> list[Aviso]:
    """Troca de óleo, avisada ao locatário do contrato ativo. Cada item: `moto_id, cliente_id, placa, situacao`
    (`proxima` ou `vencida`), `km_restantes` e `dias_restantes` (qualquer um pode ser None) e `ultima_data`
    (da última troca; a escala só conta os avisos feitos depois dela)."""
    avisos = []
    for a in alertas:
        dados = dict(placa=a.get("placa"), km_restantes=a.get("km_restantes"), dias_restantes=a.get("dias_restantes"))
        if a["situacao"] == "proxima":
            if _sem_aviso(historico, "oleo_proxima", a["moto_id"], janela_dias=cfg.reenvio_proximo_dias, dia=dia_envio):
                avisos.append(_aviso("oleo_proxima", a["cliente_id"], a["moto_id"], dia_envio, **dados))
        elif a["situacao"] == "vencida":
            datas = _datas(historico, "oleo_vencida", a["moto_id"], a.get("ultima_data"))
            if escala_devida(dia_envio, datas, cfg.max_repeticoes):
                avisos.append(_aviso("oleo_vencida", a["cliente_id"], a["moto_id"], dia_envio, **dados))
    return avisos


# -------------------------------------------------------------------- portal --


def avisos_de_portal(dia_envio: date, eventos, historico, cfg: ConfigAvisos) -> list[Aviso]:
    """Acesso criado ou senha alterada. Cada evento: `tipo` (`portal_acesso` ou `portal_senha_alterada`),
    `cliente_id`, `referencia_id` (um id único do evento) e `ocorrido_em`. Só os recentes."""
    limite = dia_envio - timedelta(days=cfg.evento_recente_dias)
    avisos = []
    for e in eventos:
        if e["tipo"] not in ("portal_acesso", "portal_senha_alterada"):
            raise ValueError(f"Tipo de evento do portal desconhecido: {e['tipo']!r}")
        if e["ocorrido_em"] >= limite and _sem_aviso(historico, e["tipo"], e["referencia_id"]):
            avisos.append(_aviso(e["tipo"], e["cliente_id"], e["referencia_id"], dia_envio))
    return avisos


def avisos_devidos(
    dia_envio: date, *, cobrancas=(), pagamentos=(), cnhs=(), documentos=(), oleo=(), portal=(),
    historico=None, cfg: ConfigAvisos | None = None,
) -> list[Aviso]:
    """Todos os avisos devidos no `dia_envio`, de todos os tipos e clientes (ainda sem agrupar)."""
    cfg = cfg or ConfigAvisos()
    historico = historico or {}
    return (
        avisos_de_cobrancas(dia_envio, cobrancas, historico, cfg)
        + avisos_de_recibos(dia_envio, pagamentos, historico, cfg)
        + avisos_de_cnh(dia_envio, cnhs, historico, cfg)
        + avisos_de_documentos(dia_envio, documentos, historico, cfg)
        + avisos_de_oleo(dia_envio, oleo, historico, cfg)
        + avisos_de_portal(dia_envio, portal, historico, cfg)
    )
