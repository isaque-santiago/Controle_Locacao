"""Regras de arquivamento de veículos vendidos e ex-locatários (src/domain/arquivamento.py)."""

from decimal import Decimal

from src.domain import arquivamento as a


def _contrato(id_, moto, cliente, status="ativo"):
    return {"id": id_, "moto_id": moto, "cliente_id": cliente, "status": status}


def _cobranca(moto, cliente, situacao="aberta", saldo="100.00"):
    return {"moto_id": moto, "cliente_id": cliente, "situacao": situacao, "saldo": saldo}


def test_moto_sem_pendencia_pode_arquivar():
    p = a.pendencias_da_moto("m1", [_contrato("c1", "m1", "k1", "encerrado")], [], [], [_cobranca("m1", "k1", "paga", "0")])
    assert p.pode_arquivar
    assert p.impedimentos() == []


def test_moto_com_contrato_ativo_nao_arquiva():
    p = a.pendencias_da_moto("m1", [_contrato("c1", "m1", "k1")], [], [], [])
    assert not p.pode_arquivar
    assert p.impedimentos() == ["1 contrato ativo"]


def test_moto_vinculada_a_contrato_ativo_conta_como_pendencia():
    contratos = [_contrato("c1", "m2", "k1")]
    p = a.pendencias_da_moto("m1", contratos, [{"contrato_id": "c1", "moto_id": "m1"}], [], [])
    assert p.contratos_ativos == 1


def test_moto_com_manutencao_aberta_nao_arquiva():
    p = a.pendencias_da_moto("m1", [], [], [{"moto_id": "m1", "status": "aberta"}, {"moto_id": "m1", "status": "concluida"}], [])
    assert p.manutencoes_abertas == 1


def test_cobranca_atrasada_ou_aberta_impede_e_soma_saldo():
    cobrancas = [_cobranca("m1", "k1", "atrasada", "150.50"), _cobranca("m1", "k1", "aberta", "49.50"),
                 _cobranca("m1", "k1", "cancelada", "80"), _cobranca("m2", "k1", "aberta", "10")]
    p = a.pendencias_da_moto("m1", [], [], [], cobrancas)
    assert p.cobrancas_abertas == 2
    assert p.saldo_aberto == Decimal("200.00")


def test_cliente_com_debito_em_contrato_encerrado_nao_arquiva():
    p = a.pendencias_do_cliente("k1", [_contrato("c1", "m1", "k1", "encerrado")], [_cobranca("m1", "k1", "atrasada")])
    assert not p.pode_arquivar
    assert p.impedimentos() == ["1 cobrança em aberto"]


def test_cliente_quitado_e_sem_contrato_ativo_pode_arquivar():
    p = a.pendencias_do_cliente("k1", [_contrato("c1", "m1", "k1", "encerrado")], [_cobranca("m1", "k1", "paga", "0")])
    assert p.pode_arquivar


def test_cliente_nao_conta_pendencia_de_outro_cliente():
    p = a.pendencias_do_cliente("k1", [_contrato("c1", "m1", "k2")], [_cobranca("m1", "k2")])
    assert p.pode_arquivar


def test_texto_da_recusa_lista_tudo_no_plural():
    p = a.Pendencias(contratos_ativos=2, manutencoes_abertas=1, cobrancas_abertas=3)
    assert a.texto_recusa(p, "o veículo") == (
        "Não é possível arquivar o veículo: 2 contratos ativos, 1 manutenção aberta, 3 cobranças em aberto."
    )


def test_esta_arquivado_para_moto_e_cliente():
    assert a.esta_arquivado({"arquivada_em": "2026-11-19T10:00:00+00:00"})
    assert a.esta_arquivado({"arquivado_em": "2026-11-19T10:00:00+00:00"})
    assert not a.esta_arquivado({"arquivada_em": None})
    assert not a.esta_arquivado({})


def test_motivo_desconhecido_vira_o_padrao():
    assert a.motivo_valido("outro") == "outro"
    assert a.motivo_valido("xyz") == a.MOTIVO_PADRAO
    assert a.motivo_valido(None) == a.MOTIVO_PADRAO
