"""Testes de src/domain/janela_envio.py: 8h às 19h, segunda a sábado, sem feriado nacional."""

from datetime import date, datetime, timezone

import pytest

from src.domain.janela_envio import (
    FUSO, dentro_da_janela, dia_de_envio, dia_de_envio_anterior, liberado_ate, proximo_dia_de_envio, proximo_horario_valido,
)


def _br(ano, mes, dia, hora=12, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


def test_dias_de_envio():
    assert dia_de_envio(date(2026, 11, 5))        # quinta
    assert dia_de_envio(date(2026, 11, 7))        # sábado
    assert not dia_de_envio(date(2026, 11, 8))    # domingo
    assert not dia_de_envio(date(2026, 11, 15))   # domingo e feriado
    assert not dia_de_envio(date(2026, 11, 20))   # sexta, Consciência Negra


@pytest.mark.parametrize("hora, minuto, esperado", [(7, 59, False), (8, 0, True), (18, 59, True), (19, 0, False), (23, 0, False)])
def test_limites_do_horario(hora, minuto, esperado):
    assert dentro_da_janela(_br(2026, 11, 5, hora, minuto)) is esperado


def test_domingo_e_feriado_fora_da_janela():
    assert not dentro_da_janela(_br(2026, 11, 8, 10))
    assert not dentro_da_janela(_br(2026, 11, 20, 10))


def test_horario_dentro_da_janela_nao_muda():
    assert proximo_horario_valido(_br(2026, 11, 5, 10, 30)) == _br(2026, 11, 5, 10, 30)


def test_antes_da_abertura_vai_para_as_8h_do_mesmo_dia():
    assert proximo_horario_valido(_br(2026, 11, 5, 6, 0)) == _br(2026, 11, 5, 8, 0)


def test_depois_do_fechamento_vai_para_as_8h_do_dia_seguinte():
    assert proximo_horario_valido(_br(2026, 11, 5, 19, 0)) == _br(2026, 11, 6, 8, 0)


def test_sabado_a_noite_vai_para_segunda():
    assert proximo_horario_valido(_br(2026, 11, 7, 20, 0)) == _br(2026, 11, 9, 8, 0)


def test_domingo_vai_para_segunda():
    assert proximo_horario_valido(_br(2026, 11, 8, 9, 0)) == _br(2026, 11, 9, 8, 0)


def test_feriado_vai_para_o_proximo_dia_util():
    # 15/11/2026 é domingo e feriado; 16/11 é segunda.
    assert proximo_horario_valido(_br(2026, 11, 15, 10, 0)) == _br(2026, 11, 16, 8, 0)
    # Sexta-feira Santa (3/4/2026): sábado 4/4 tem envio.
    assert proximo_horario_valido(_br(2026, 4, 3, 10, 0)) == _br(2026, 4, 4, 8, 0)


def test_feriado_seguido_de_domingo():
    # 20/11/2026 (sexta, feriado): sábado 21 tem envio.
    assert proximo_horario_valido(_br(2026, 11, 20, 9, 0)) == _br(2026, 11, 21, 8, 0)
    # 1/1/2027 é sexta (feriado); sábado 2 tem envio.
    assert proximo_horario_valido(_br(2027, 1, 1, 9, 0)) == _br(2027, 1, 2, 8, 0)


def test_converte_utc_para_o_horario_de_brasilia():
    # 10h UTC = 7h em Brasília (sem horário de verão desde 2019): ainda fechado.
    momento = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)
    assert not dentro_da_janela(momento)
    assert proximo_horario_valido(momento) == _br(2026, 11, 5, 8, 0)


def test_exige_fuso_horario():
    with pytest.raises(ValueError):
        dentro_da_janela(datetime(2026, 11, 5, 10, 0))


def test_proximo_dia_de_envio_e_dia_anterior():
    assert proximo_dia_de_envio(date(2026, 11, 8)) == date(2026, 11, 9)
    assert proximo_dia_de_envio(date(2026, 11, 9)) == date(2026, 11, 9)
    # Antes de segunda 9/11 o último dia com envio é sábado 7/11.
    assert dia_de_envio_anterior(date(2026, 11, 9)) == date(2026, 11, 7)
    assert dia_de_envio_anterior(date(2026, 11, 10)) == date(2026, 11, 9)
    # Antes de 16/11 (domingo 15 é feriado e domingo): sábado 14.
    assert dia_de_envio_anterior(date(2026, 11, 16)) == date(2026, 11, 14)


def test_portao_libera_25_minutos_a_frente():
    assert liberado_ate(_br(2026, 11, 5, 10, 0)) == _br(2026, 11, 5, 10, 25)


def test_portao_nunca_passa_do_fechamento_da_janela():
    assert liberado_ate(_br(2026, 11, 5, 18, 50)) == _br(2026, 11, 5, 19, 0)
    assert liberado_ate(_br(2026, 11, 5, 18, 59)) == _br(2026, 11, 5, 19, 0)
    assert liberado_ate(_br(2026, 11, 5, 18, 30)) == _br(2026, 11, 5, 18, 55)


def test_portao_fechado_fora_da_janela():
    assert liberado_ate(_br(2026, 11, 5, 7, 59)) is None     # antes da abertura
    assert liberado_ate(_br(2026, 11, 5, 19, 0)) is None     # no fechamento
    assert liberado_ate(_br(2026, 11, 8, 10, 0)) is None     # domingo
    assert liberado_ate(_br(2026, 11, 20, 10, 0)) is None    # feriado nacional (Consciência Negra)


def test_portao_abre_exatamente_as_8h_e_aceita_outra_folga():
    from datetime import timedelta

    assert liberado_ate(_br(2026, 11, 5, 8, 0)) == _br(2026, 11, 5, 8, 25)
    assert liberado_ate(_br(2026, 11, 5, 10, 0), folga=timedelta(minutes=10)) == _br(2026, 11, 5, 10, 10)


def test_portao_converte_de_utc_e_exige_fuso():
    assert liberado_ate(datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)) == _br(2026, 11, 5, 10, 25)
    with pytest.raises(ValueError):
        liberado_ate(datetime(2026, 11, 5, 10, 0))

