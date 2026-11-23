"""Serviços de arquivamento: conferem o estado e as pendências antes de chamar a RPC."""

from datetime import date

import pytest

from src.services import clientes, motos


def _moto(**extra):
    return {"id": "m1", "status": "disponivel", "arquivada_em": None, **extra}


@pytest.fixture
def banco(monkeypatch):
    chamadas = []
    estado = {"moto": _moto(), "cliente": {"id": "k1", "arquivado_em": None}, "contratos": [], "vinculos": [],
              "manutencoes": [], "cobrancas": []}
    monkeypatch.setattr(motos.motos, "obter", lambda id_: estado["moto"])
    monkeypatch.setattr(motos.contratos, "listar", lambda: estado["contratos"])
    monkeypatch.setattr(motos.contratos, "listar_vinculos", lambda: estado["vinculos"])
    monkeypatch.setattr(motos.manutencoes, "listar", lambda moto_id=None: estado["manutencoes"])
    monkeypatch.setattr(motos.cobrancas, "listar", lambda: estado["cobrancas"])
    monkeypatch.setattr(motos.motos, "arquivar_via_rpc", lambda *a: chamadas.append(("arquivar_moto", *a)) or {})
    monkeypatch.setattr(motos.motos, "desarquivar_via_rpc", lambda *a: chamadas.append(("desarquivar_moto", *a)) or {})
    monkeypatch.setattr(clientes.clientes, "obter", lambda id_: estado["cliente"])
    monkeypatch.setattr(clientes.contratos, "listar", lambda: estado["contratos"])
    monkeypatch.setattr(clientes.cobrancas, "listar", lambda: estado["cobrancas"])
    monkeypatch.setattr(clientes.clientes, "arquivar_via_rpc", lambda *a: chamadas.append(("arquivar_cliente", *a)) or {})
    return estado, chamadas


def test_arquiva_moto_vendida_sem_pendencias(banco):
    _, chamadas = banco
    motos.arquivar("m1", "vendida", date(2026, 11, 10))
    assert chamadas == [("arquivar_moto", "m1", "vendida", "2026-11-10")]


def test_outro_motivo_nao_leva_data_de_venda(banco):
    _, chamadas = banco
    motos.arquivar("m1", "outro", date(2026, 11, 10))
    assert chamadas == [("arquivar_moto", "m1", "outro", None)]


def test_moto_com_pendencia_nao_chama_a_rpc(banco):
    estado, chamadas = banco
    estado["cobrancas"] = [{"moto_id": "m1", "cliente_id": "k1", "situacao": "atrasada", "saldo": "50"}]
    with pytest.raises(ValueError, match="1 cobrança em aberto"):
        motos.arquivar("m1", "vendida", date(2026, 11, 10))
    assert chamadas == []


def test_moto_alugada_ou_ja_arquivada_e_recusada(banco):
    estado, chamadas = banco
    estado["moto"] = _moto(status="alugada")
    with pytest.raises(ValueError, match="em uso"):
        motos.arquivar("m1", "vendida")
    estado["moto"] = _moto(status="inativa", arquivada_em="2026-11-10T10:00:00+00:00")
    with pytest.raises(ValueError, match="já está arquivado"):
        motos.arquivar("m1", "vendida")
    assert chamadas == []


def test_arquiva_cliente_quitado(banco):
    _, chamadas = banco
    clientes.arquivar("k1")
    assert chamadas == [("arquivar_cliente", "k1")]


def test_cliente_com_debito_de_contrato_encerrado_nao_arquiva(banco):
    estado, chamadas = banco
    estado["contratos"] = [{"id": "c1", "moto_id": "m1", "cliente_id": "k1", "status": "encerrado"}]
    estado["cobrancas"] = [{"moto_id": "m1", "cliente_id": "k1", "situacao": "atrasada", "saldo": "300"}]
    with pytest.raises(ValueError, match="o cliente: 1 cobrança em aberto"):
        clientes.arquivar("k1")
    assert chamadas == []


def test_cliente_ja_arquivado_e_recusado(banco):
    estado, _ = banco
    estado["cliente"] = {"id": "k1", "arquivado_em": "2026-11-10T10:00:00+00:00"}
    with pytest.raises(ValueError, match="já está arquivado"):
        clientes.arquivar("k1")
