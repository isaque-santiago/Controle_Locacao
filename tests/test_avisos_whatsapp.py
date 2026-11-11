"""Testes de src/domain/avisos_whatsapp.py: quais avisos de WhatsApp são devidos em cada dia de envio."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.domain.avisos_whatsapp import (
    ConfigAvisos, avisos_de_cnh, avisos_de_cobrancas, avisos_de_documentos, avisos_de_oleo, avisos_de_portal,
    avisos_de_recibos, avisos_devidos, escala_devida,
)

CFG = ConfigAvisos(multa_atraso=Decimal("15.00"), encargo_diario=Decimal("7.00"), dias_inadimplencia=15)
CLIENTE = "cli-1"


def _cobranca(id="cob-1", vencimento=date(2026, 11, 10), saldo="450.00", periodicidade="semanal",
              situacao="aberta", tipo="locacao", cliente_id=CLIENTE):
    return {"id": id, "cliente_id": cliente_id, "tipo": tipo, "vencimento": vencimento, "saldo": Decimal(saldo),
            "periodicidade": periodicidade, "situacao": situacao, "placa": "ABC1D23"}


def _tipos(avisos):
    return [a.tipo for a in avisos]


# ------------------------------------------------------------------- escala --


def test_escala_sem_aviso_anterior_e_devida():
    assert escala_devida(date(2026, 11, 11), [])


def test_escala_dias_1_3_7_e_depois_a_cada_3_dias_com_teto_de_10():
    vencimento = date(2026, 11, 10)
    enviados = []
    for dias in range(1, 40):
        dia = vencimento + timedelta(days=dias)
        if escala_devida(dia, enviados, 10):
            enviados.append(dia)
    assert [(d - vencimento).days for d in enviados] == [1, 3, 7, 10, 13, 16, 19, 22, 25, 28]


def test_escala_nunca_dois_no_mesmo_dia_nem_antes_do_prazo():
    primeiro = date(2026, 11, 11)
    assert not escala_devida(primeiro, [primeiro])                      # já saiu hoje
    assert not escala_devida(primeiro + timedelta(days=1), [primeiro])  # dia 2: cedo
    assert escala_devida(primeiro + timedelta(days=2), [primeiro])      # dia 3


def test_escala_dia_perdido_recupera_sem_inundar():
    primeiro = date(2026, 11, 11)
    # sistema ficou parado: no dia 9 ainda falta o "dia 3" e o "dia 7"; sai um por vez, com 2+ dias entre eles
    enviados = [primeiro]
    dia = primeiro + timedelta(days=8)
    assert escala_devida(dia, enviados)
    enviados.append(dia)
    assert not escala_devida(dia + timedelta(days=1), enviados)
    assert escala_devida(dia + timedelta(days=2), enviados)


def test_escala_respeita_o_maximo():
    datas = [date(2026, 11, 1) + timedelta(days=3 * i) for i in range(3)]
    assert not escala_devida(date(2026, 12, 30), datas, maximo=3)
    assert not escala_devida(date(2026, 12, 30), [], maximo=0)


# ---------------------------------------------------------------- cobranças --


def test_lembrete_de_vespera_no_dia_anterior():
    avisos = avisos_de_cobrancas(date(2026, 11, 9), [_cobranca()], {}, CFG)  # vence terça 10/11; segunda 9/11
    assert _tipos(avisos) == ["lembrete_vespera"]
    assert avisos[0].dados["dias_ate_vencer"] == 1
    assert avisos[0].data_referencia == date(2026, 11, 9)


def test_vencimento_na_segunda_e_lembrado_no_sabado():
    venc = date(2026, 11, 9)  # segunda; domingo não tem envio
    assert _tipos(avisos_de_cobrancas(date(2026, 11, 7), [_cobranca(vencimento=venc)], {}, CFG)) == ["lembrete_vespera"]
    assert avisos_de_cobrancas(date(2026, 11, 6), [_cobranca(vencimento=venc)], {}, CFG) == []
    assert avisos_de_cobrancas(date(2026, 11, 8), [_cobranca(vencimento=venc)], {}, CFG) == []


def test_vencimento_em_feriado_e_lembrado_no_ultimo_dia_de_envio_antes():
    venc = date(2026, 11, 20)  # sexta, Consciência Negra
    avisos = avisos_de_cobrancas(date(2026, 11, 19), [_cobranca(vencimento=venc)], {}, CFG)
    assert _tipos(avisos) == ["lembrete_vespera"]


def test_contrato_diario_so_recebe_lembrete_no_dia():
    c = _cobranca(periodicidade="diario")
    assert avisos_de_cobrancas(date(2026, 11, 9), [c], {}, CFG) == []
    assert _tipos(avisos_de_cobrancas(date(2026, 11, 10), [c], {}, CFG)) == ["lembrete_vencimento"]


def test_lembrete_no_dia_do_vencimento():
    assert _tipos(avisos_de_cobrancas(date(2026, 11, 10), [_cobranca()], {}, CFG)) == ["lembrete_vencimento"]


def test_lembretes_saem_uma_vez_so():
    historico = {("lembrete_vespera", "cob-1"): [date(2026, 11, 9)], ("lembrete_vencimento", "cob-1"): [date(2026, 11, 10)]}
    assert avisos_de_cobrancas(date(2026, 11, 9), [_cobranca()], historico, CFG) == []
    assert avisos_de_cobrancas(date(2026, 11, 10), [_cobranca()], historico, CFG) == []


def test_atraso_traz_encargos_do_dia_de_envio():
    # 3 dias de atraso: multa de R$ 15 + 3 x R$ 7 = R$ 36; saldo R$ 450 -> total R$ 486
    avisos = avisos_de_cobrancas(date(2026, 11, 13), [_cobranca(situacao="atrasada")], {}, CFG)
    assert _tipos(avisos) == ["atraso"]
    dados = avisos[0].dados
    assert dados["dias_atraso"] == 3
    assert dados["encargos"] == Decimal("36.00")
    assert dados["total"] == Decimal("486.00")


def test_atraso_em_pagamento_parcial_usa_o_saldo_restante():
    avisos = avisos_de_cobrancas(date(2026, 11, 11), [_cobranca(situacao="atrasada", saldo="200.00")], {}, CFG)
    assert avisos[0].dados["saldo"] == Decimal("200.00")
    assert avisos[0].dados["total"] == Decimal("222.00")  # 200 + 15 + 7


def test_atraso_segue_a_escala_pelo_historico():
    c = _cobranca(situacao="atrasada")
    historico = {("atraso", "cob-1"): [date(2026, 11, 11)]}
    assert avisos_de_cobrancas(date(2026, 11, 12), [c], historico, CFG) == []   # dia 2
    assert _tipos(avisos_de_cobrancas(date(2026, 11, 13), [c], historico, CFG)) == ["atraso"]  # dia 3


def test_cobranca_paga_cancelada_ou_sem_saldo_nao_gera_aviso():
    for situacao in ("paga", "cancelada"):
        assert avisos_de_cobrancas(date(2026, 11, 13), [_cobranca(situacao=situacao)], {}, CFG) == []
    assert avisos_de_cobrancas(date(2026, 11, 13), [_cobranca(situacao="atrasada", saldo="0")], {}, CFG) == []


def test_encargos_so_em_cobranca_de_locacao():
    dados = avisos_de_cobrancas(date(2026, 11, 13), [_cobranca(situacao="atrasada", tipo="dano")], {}, CFG)[0].dados
    assert dados["encargos"] == Decimal("0.00") and dados["total"] == Decimal("450.00")


def test_inadimplencia_no_corte_e_uma_vez_so():
    c = _cobranca(situacao="atrasada")
    dia = date(2026, 11, 25)  # 15 dias de atraso
    assert "inadimplencia" in _tipos(avisos_de_cobrancas(dia, [c], {}, CFG))
    assert "inadimplencia" not in _tipos(avisos_de_cobrancas(date(2026, 11, 24), [c], {}, CFG))
    historico = {("inadimplencia", "cob-1"): [dia]}
    assert "inadimplencia" not in _tipos(avisos_de_cobrancas(date(2026, 11, 26), [c], historico, CFG))


def test_inadimplencia_usa_o_corte_das_configuracoes():
    cfg = ConfigAvisos(dias_inadimplencia=3)
    assert "inadimplencia" in _tipos(avisos_de_cobrancas(date(2026, 11, 13), [_cobranca(situacao="atrasada")], {}, cfg))


def test_vencimento_em_mes_curto_e_virada_de_ano():
    venc = date(2027, 3, 1)  # segunda, depois de fevereiro de 28 dias
    assert _tipos(avisos_de_cobrancas(date(2027, 2, 27), [_cobranca(vencimento=venc)], {}, CFG)) == ["lembrete_vespera"]
    venc = date(2027, 1, 4)  # segunda; 1/1 é feriado (sexta) e 2/1 é sábado (tem envio)
    assert _tipos(avisos_de_cobrancas(date(2027, 1, 2), [_cobranca(vencimento=venc)], {}, CFG)) == ["lembrete_vespera"]


# ------------------------------------------------------------------- recibo --


def _pagamento(id="pag-1", data=date(2026, 11, 10), valor="450.00", restante="0"):
    return {"id": id, "cliente_id": CLIENTE, "data_pagamento": data, "valor": Decimal(valor),
            "placa": "ABC1D23", "vencimento": date(2026, 11, 10), "saldo_restante": Decimal(restante)}


def test_recibo_do_pagamento_recente():
    avisos = avisos_de_recibos(date(2026, 11, 10), [_pagamento()], {}, CFG)
    assert _tipos(avisos) == ["recibo_pagamento"]
    assert avisos[0].dados["valor"] == Decimal("450.00")


def test_recibo_de_pagamento_parcial_traz_o_saldo():
    avisos = avisos_de_recibos(date(2026, 11, 10), [_pagamento(valor="200.00", restante="250.00")], {}, CFG)
    assert avisos[0].dados["saldo_restante"] == Decimal("250.00")


def test_recibo_nao_sai_de_pagamento_antigo_nem_repetido():
    assert avisos_de_recibos(date(2026, 11, 20), [_pagamento()], {}, CFG) == []
    assert avisos_de_recibos(date(2026, 11, 10), [_pagamento()], {("recibo_pagamento", "pag-1"): [date(2026, 11, 10)]}, CFG) == []


# --------------------------------------------------------------------- CNH --


def test_cnh_proxima_uma_vez_por_janela():
    cnh = {"cliente_id": CLIENTE, "cnh_validade": date(2026, 11, 30), "situacao": "a_vencer"}
    dia = date(2026, 11, 10)
    assert _tipos(avisos_de_cnh(dia, [cnh], {}, CFG)) == ["cnh_proxima"]
    assert avisos_de_cnh(dia + timedelta(days=5), [cnh], {("cnh_proxima", CLIENTE): [dia]}, CFG) == []
    # ainda "a vencer" 31 dias depois (validade mais distante e antecedência maior): avisa de novo
    longe = dict(cnh, cnh_validade=date(2027, 1, 20))
    assert _tipos(avisos_de_cnh(dia + timedelta(days=31), [longe], {("cnh_proxima", CLIENTE): [dia]}, CFG)) == ["cnh_proxima"]


def test_cnh_vencida_segue_a_escala_a_partir_do_primeiro_aviso():
    cnh = {"cliente_id": CLIENTE, "cnh_validade": date(2026, 11, 1), "situacao": "vencida"}
    assert _tipos(avisos_de_cnh(date(2026, 11, 2), [cnh], {}, CFG)) == ["cnh_vencida"]
    historico = {("cnh_vencida", CLIENTE): [date(2026, 11, 2)]}
    assert avisos_de_cnh(date(2026, 11, 3), [cnh], historico, CFG) == []
    assert _tipos(avisos_de_cnh(date(2026, 11, 4), [cnh], historico, CFG)) == ["cnh_vencida"]


def test_cnh_renovada_reinicia_o_ciclo_do_aviso_de_vencida():
    # avisos do ciclo anterior (antes da nova validade) não contam contra o teto do ciclo atual
    antigos = [date(2025, 1, 1) + timedelta(days=3 * i) for i in range(10)]
    cnh = {"cliente_id": CLIENTE, "cnh_validade": date(2026, 11, 1), "situacao": "vencida"}
    assert _tipos(avisos_de_cnh(date(2026, 11, 2), [cnh], {("cnh_vencida", CLIENTE): antigos}, CFG)) == ["cnh_vencida"]


# --------------------------------------------------------------- documentos --


def _documento(situacao="vencido", vencimento=date(2026, 11, 5), tipo="ipva"):
    return {"id": "doc-1", "cliente_id": CLIENTE, "placa": "ABC1D23", "tipo_documento": tipo, "descricao": None,
            "vencimento": vencimento, "situacao": situacao}


def test_documento_vencido_segue_a_escala():
    assert _tipos(avisos_de_documentos(date(2026, 11, 6), [_documento()], {}, CFG)) == ["documento_vencido"]
    historico = {("documento_vencido", "doc-1"): [date(2026, 11, 6)]}
    assert avisos_de_documentos(date(2026, 11, 7), [_documento()], historico, CFG) == []
    assert _tipos(avisos_de_documentos(date(2026, 11, 8), [_documento()], historico, CFG)) == ["documento_vencido"]


def test_documento_a_vencer_avisa_uma_vez():
    doc = _documento(situacao="a_vencer", vencimento=date(2026, 11, 20))
    assert _tipos(avisos_de_documentos(date(2026, 11, 10), [doc], {}, CFG)) == ["documento_proximo"]
    assert avisos_de_documentos(date(2026, 11, 11), [doc], {("documento_proximo", "doc-1"): [date(2026, 11, 10)]}, CFG) == []


def test_documento_com_comprovante_aguardando_nao_e_avisado():
    """O locatário já mandou o comprovante: insistir seria à toa até o dono conferir. Recusado, o aviso volta."""
    for situacao, vencimento in (("vencido", date(2026, 11, 5)), ("a_vencer", date(2026, 11, 20))):
        doc = _documento(situacao=situacao, vencimento=vencimento)
        assert avisos_de_documentos(date(2026, 11, 10), [dict(doc, comprovante_enviado=True)], {}, CFG) == []
        assert len(avisos_de_documentos(date(2026, 11, 10), [dict(doc, comprovante_enviado=False)], {}, CFG)) == 1
        assert len(avisos_de_documentos(date(2026, 11, 10), [doc], {}, CFG)) == 1  # campo ausente (banco antigo): avisa


def test_so_o_documento_com_comprovante_pausa_nao_os_outros_do_cliente():
    pausado = dict(_documento(), id="doc-1", comprovante_enviado=True)
    outro = dict(_documento(tipo="seguro"), id="doc-2")
    avisos = avisos_de_documentos(date(2026, 11, 10), [pausado, outro], {}, CFG)
    assert [a.referencia_id for a in avisos] == ["doc-2"]


# --------------------------------------------------------------------- óleo --


def test_oleo_proxima_e_vencida():
    base = {"moto_id": "moto-1", "cliente_id": CLIENTE, "placa": "ABC1D23", "km_restantes": 300, "dias_restantes": None,
            "ultima_data": date(2026, 9, 1)}
    assert _tipos(avisos_de_oleo(date(2026, 11, 10), [dict(base, situacao="proxima")], {}, CFG)) == ["oleo_proxima"]
    assert _tipos(avisos_de_oleo(date(2026, 11, 10), [dict(base, situacao="vencida")], {}, CFG)) == ["oleo_vencida"]
    assert avisos_de_oleo(date(2026, 11, 10), [dict(base, situacao="em_dia")], {}, CFG) == []


def test_oleo_vencida_ignora_avisos_de_antes_da_ultima_troca():
    base = {"moto_id": "moto-1", "cliente_id": CLIENTE, "placa": "ABC1D23", "situacao": "vencida",
            "km_restantes": -50, "dias_restantes": None, "ultima_data": date(2026, 9, 1)}
    antigos = [date(2026, 3, 1) + timedelta(days=3 * i) for i in range(10)]
    assert _tipos(avisos_de_oleo(date(2026, 11, 10), [base], {("oleo_vencida", "moto-1"): antigos}, CFG)) == ["oleo_vencida"]


# ------------------------------------------------------------------- portal --


def test_portal_acesso_e_senha_alterada_recentes():
    eventos = [
        {"tipo": "portal_acesso", "cliente_id": CLIENTE, "referencia_id": "ev-1", "ocorrido_em": date(2026, 11, 10)},
        {"tipo": "portal_senha_alterada", "cliente_id": CLIENTE, "referencia_id": "ev-2", "ocorrido_em": date(2026, 11, 10)},
        {"tipo": "portal_acesso", "cliente_id": CLIENTE, "referencia_id": "ev-3", "ocorrido_em": date(2026, 9, 1)},
    ]
    assert _tipos(avisos_de_portal(date(2026, 11, 10), eventos, {}, CFG)) == ["portal_acesso", "portal_senha_alterada"]


def test_portal_tipo_desconhecido_e_erro():
    with pytest.raises(ValueError):
        avisos_de_portal(date(2026, 11, 10), [{"tipo": "x", "cliente_id": CLIENTE, "referencia_id": "e", "ocorrido_em": date(2026, 11, 10)}], {}, CFG)


# ------------------------------------------------------------------ conjunto --


def test_avisos_devidos_junta_assuntos_de_varios_tipos_e_clientes():
    cobrancas = [_cobranca(situacao="atrasada"), _cobranca(id="cob-2", cliente_id="cli-2", vencimento=date(2026, 11, 13))]
    cnhs = [{"cliente_id": CLIENTE, "cnh_validade": date(2026, 11, 20), "situacao": "a_vencer"}]
    avisos = avisos_devidos(date(2026, 11, 13), cobrancas=cobrancas, cnhs=cnhs, cfg=CFG)
    assert sorted((a.cliente_id, a.tipo) for a in avisos) == [
        ("cli-1", "atraso"), ("cli-1", "cnh_proxima"), ("cli-2", "lembrete_vencimento")]
