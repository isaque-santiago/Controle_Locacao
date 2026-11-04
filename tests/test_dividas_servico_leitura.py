"""Serviço de dívidas (leitura): resumo da lista e ficha de uma dívida."""

from decimal import Decimal
from types import SimpleNamespace

from src.services import dividas


def _preparar(monkeypatch, divida=True):
    saldos = [
        {"divida_id": "d1", "credor": "Celta", "tipo": "compra_parcelada", "saldo_calculado": "3000", "saldo_confirmado": None,
         "total_pago": "11000", "valor_original": "14000", "moto_id": "m1", "diferenca": None},
        {"divida_id": "d2", "credor": "Etios", "tipo": "emprestimo", "saldo_calculado": "0", "saldo_confirmado": None,
         "total_pago": "100", "valor_original": "100", "moto_id": None, "diferenca": None},
    ]
    parcelas = [
        {"divida_id": "d1", "vencimento_id": "v1", "numero": 8, "vencimento": "2026-11-28", "valor": "1000", "valor_pago": "0",
         "saldo": "1000", "situacao": "a_vencer"},
        {"divida_id": "d1", "vencimento_id": "v0", "numero": 7, "vencimento": "2026-10-28", "valor": "1000", "valor_pago": "1000",
         "saldo": "0", "situacao": "paga"},
    ]
    repo = SimpleNamespace(
        listar_saldos=lambda: saldos,
        listar_todas_parcelas=lambda: parcelas,
        obter=lambda id: ({"id": id, "tipo": "compra_parcelada", "credor": "Celta", "moto_id": "m1", "valor_original": "14000"} if divida and id == "d1" else None),
        listar_parcelas=lambda id: sorted([p for p in parcelas if p["divida_id"] == id], key=lambda p: p["numero"]),
        listar_pagamentos=lambda id: [{"id": "p1", "data": "2026-10-28", "valor": "1000", "vencimento_id": "v0"},
                                      {"id": "p2", "data": "2026-05-01", "valor": "5000", "vencimento_id": None}],
        obter_parcela=lambda id: next((p for p in parcelas if p["vencimento_id"] == id), None),
    )
    monkeypatch.setattr(dividas, "dividas", repo)
    monkeypatch.setattr(dividas, "motos", SimpleNamespace(
        listar=lambda: [{"id": "m1", "placa": "OID7656"}], obter=lambda id: {"id": id, "placa": "OID7656", "modelo": "Celta"}))
    monkeypatch.setattr(dividas, "contas", SimpleNamespace(listar_ativas=lambda: [{"id": "c1", "nome": "Quezia"}]))


def test_resumo_traz_linhas_com_placa_e_totais(monkeypatch):
    _preparar(monkeypatch)
    r = dividas.resumo()
    assert [l["credor"] for l in r["linhas"]] == ["Celta", "Etios"]
    assert r["linhas"][0]["placa"] == "OID7656" and r["linhas"][1]["placa"] is None
    assert r["linhas"][0]["proxima_vencimento"].isoformat() == "2026-11-28"
    assert r["totais"]["total_em_aberto"] == Decimal("3000") and r["totais"]["dividas_em_aberto"] == 1


def test_ficha_junta_parcelas_pagamentos_e_moto(monkeypatch):
    _preparar(monkeypatch)
    f = dividas.ficha("d1")
    assert f["tipo_rotulo"] == "Compra parcelada" and f["saldo"] == Decimal("3000") and f["total_pago"] == Decimal("11000")
    assert [p["numero"] for p in f["parcelas"]] == [7, 8] and f["pagamentos"][0]["id"] == "p1"
    assert f["pagamentos"][0]["parcela_numero"] == 7 and f["pagamentos"][1]["parcela_numero"] is None
    assert f["moto"]["placa"] == "OID7656"


def test_ficha_de_divida_inexistente_e_none(monkeypatch):
    _preparar(monkeypatch)
    assert dividas.ficha("nao-existe") is None


def test_parcela_e_contas(monkeypatch):
    _preparar(monkeypatch)
    assert dividas.parcela("v1")["numero"] == 8 and dividas.parcela("x") is None
    assert dividas.contas_ativas() == [{"id": "c1", "nome": "Quezia"}]
