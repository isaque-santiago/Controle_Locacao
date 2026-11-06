"""Testes de src/domain/dados_whatsapp.py: a leitura em JSON vira os tipos das regras."""

from datetime import date
from decimal import Decimal

from src.domain.avisos_whatsapp import avisos_devidos
from src.domain.dados_whatsapp import clientes_da_leitura, config_do_envio, entradas_das_regras

BRUTO = {
    "config": {"ativo": True, "modo_teste": False, "numero_teste": None, "max_repeticoes": 10, "dias_inadimplencia": 15,
               "multa_atraso": "15.00", "encargo_diario": "7.00"},
    "cobrancas": [{"id": "cob-1", "cliente_id": "cli-1", "tipo": "locacao", "vencimento": "2026-11-10", "saldo": "450.00",
                   "periodicidade": "semanal", "situacao": "atrasada", "placa": "ABC1D23"}],
    "pagamentos": [{"id": "pag-1", "cliente_id": "cli-1", "data_pagamento": "2026-11-13", "valor": "100.00", "placa": "ABC1D23",
                    "vencimento": "2026-11-10", "saldo_restante": "350.00"}],
    "cnhs": [{"cliente_id": "cli-1", "cnh_validade": "2026-11-20", "situacao": "a_vencer"}],
    "documentos": [{"id": "doc-1", "cliente_id": "cli-1", "placa": "ABC1D23", "tipo_documento": "ipva", "descricao": None,
                    "vencimento": "2026-11-05", "situacao": "vencido"}],
    "oleo": [{"moto_id": "moto-1", "cliente_id": "cli-1", "placa": "ABC1D23", "situacao": "vencida",
              "km_restantes": -20, "dias_restantes": None, "ultima_data": None}],
    "portal": [{"tipo": "portal_acesso", "cliente_id": "cli-1", "referencia_id": "u-1", "ocorrido_em": "2026-11-12"}],
    "clientes": [{"id": "cli-1", "nome": "Maria Souza", "whatsapp": "(11) 98888-7777"}],
    "historico": [{"tipo": "atraso", "referencia_id": "cob-1", "data_referencia": "2026-11-11"}],
}


def test_config_converte_tipos():
    c = config_do_envio(BRUTO)
    assert c["ativo"] is True and c["modo_teste"] is False
    assert c["avisos"].multa_atraso == Decimal("15.00") and c["avisos"].encargo_diario == Decimal("7.00")
    assert c["avisos"].dias_inadimplencia == 15 and c["avisos"].max_repeticoes == 10


def test_na_duvida_e_modo_teste():
    bruto = {"config": dict(BRUTO["config"])}
    del bruto["config"]["modo_teste"]
    assert config_do_envio(bruto)["modo_teste"] is True


def test_entradas_convertidas_e_historico_agrupado():
    e = entradas_das_regras(BRUTO)
    assert e["cobrancas"][0]["vencimento"] == date(2026, 11, 10) and e["cobrancas"][0]["saldo"] == Decimal("450.00")
    assert e["pagamentos"][0]["saldo_restante"] == Decimal("350.00")
    assert e["oleo"][0]["ultima_data"] is None
    assert e["historico"] == {("atraso", "cob-1"): [date(2026, 11, 11)]}


def test_clientes():
    assert clientes_da_leitura(BRUTO) == {"cli-1": {"nome": "Maria Souza", "whatsapp": "(11) 98888-7777"}}


def test_a_leitura_alimenta_as_regras_de_ponta_a_ponta():
    cfg = config_do_envio(BRUTO)["avisos"]
    avisos = avisos_devidos(date(2026, 11, 13), cfg=cfg, **entradas_das_regras(BRUTO))
    # atraso no dia 3 (já houve o do dia 1), recibo, CNH, documento vencido, óleo vencida e acesso ao portal
    assert sorted(a.tipo for a in avisos) == [
        "atraso", "cnh_proxima", "documento_vencido", "oleo_vencida", "portal_acesso", "recibo_pagamento"]
