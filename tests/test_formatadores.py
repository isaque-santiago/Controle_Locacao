from datetime import date, datetime
from decimal import Decimal

from src.ui.formatadores import (
    formatar_data,
    formatar_moeda,
    formatar_moeda_compacta,
    formatar_placa,
    mascarar_cpf,
)


def test_formatar_moeda_pt_br():
    assert formatar_moeda(Decimal("1234.5")) == "R$ 1.234,50"
    assert formatar_moeda(None) == "R$ 0,00"


def test_formatar_moeda_compacta_sem_centavos():
    assert formatar_moeda_compacta(Decimal("8420.30")) == "R$ 8.420"
    assert formatar_moeda_compacta(Decimal("640")) == "R$ 640"
    assert formatar_moeda_compacta(None) == "R$ 0"


def test_formatar_data_aceita_data_datetime_e_iso():
    assert formatar_data(date(2026, 9, 21)) == "21/09/2026"
    assert formatar_data(datetime(2026, 9, 21, 14, 30)) == "21/09/2026"
    assert formatar_data("2026-09-21T14:30:00") == "21/09/2026"


def test_formatar_placa():
    assert formatar_placa("abc1d23") == "ABC-1D23"


def test_mascarar_cpf():
    assert mascarar_cpf("52998224725") == "***.982.***-**"
