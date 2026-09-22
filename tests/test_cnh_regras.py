from datetime import date

from src.domain.cnh_regras import situacao_cnh


def test_sem_validade_cadastrada():
    assert situacao_cnh(None, date(2026, 9, 22), 30) == "sem_cnh"


def test_cnh_vencida():
    assert situacao_cnh(date(2026, 9, 1), date(2026, 9, 22), 30) == "vencida"


def test_cnh_a_vencer_dentro_do_limite():
    assert situacao_cnh(date(2026, 10, 10), date(2026, 9, 22), 30) == "a_vencer"


def test_cnh_em_dia_fora_do_limite():
    assert situacao_cnh(date(2027, 1, 1), date(2026, 9, 22), 30) == "em_dia"


def test_cnh_no_limite_exato_conta_como_a_vencer():
    assert situacao_cnh(date(2026, 10, 22), date(2026, 9, 22), 30) == "a_vencer"
