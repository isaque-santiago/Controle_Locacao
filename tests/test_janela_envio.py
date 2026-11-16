"""Testes de src/domain/janela_envio.py: disparos às 7:30, 11:30 e 15:00, segunda a sábado, sem feriado nacional."""

from datetime import date, datetime, timezone

import pytest

from src.domain.janela_envio import (
    FUSO, dentro_da_janela, dia_de_envio, dia_de_envio_anterior, proximo_dia_de_envio, proximo_horario_valido,
)


def _br(ano, mes, dia, hora=12, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


def test_dias_de_envio():
    assert dia_de_envio(date(2026, 11, 5))        # quinta
    assert dia_de_envio(date(2026, 11, 7))        # sábado
    assert not dia_de_envio(date(2026, 11, 8))    # domingo
    assert not dia_de_envio(date(2026, 11, 15))   # domingo e feriado
    assert not dia_de_envio(date(2026, 11, 20))   # sexta, Consciência Negra


@pytest.mark.parametrize("hora, minuto, esperado", [
    (7, 29, False), (7, 30, True), (8, 29, True), (8, 30, False),      # disparo das 7:30 (aberto por 1 hora)
    (11, 29, False), (11, 30, True), (12, 29, True), (12, 30, False),  # disparo das 11:30
    (14, 59, False), (15, 0, True), (15, 59, True), (16, 0, False),    # disparo das 15:00
    (10, 0, False), (23, 0, False),
])
def test_limites_dos_disparos(hora, minuto, esperado):
    assert dentro_da_janela(_br(2026, 11, 5, hora, minuto)) is esperado


def test_domingo_e_feriado_fora_da_janela():
    assert not dentro_da_janela(_br(2026, 11, 8, 11, 30))
    assert not dentro_da_janela(_br(2026, 11, 20, 11, 30))


def test_horario_dentro_de_um_disparo_nao_muda():
    assert proximo_horario_valido(_br(2026, 11, 5, 11, 50)) == _br(2026, 11, 5, 11, 50)


def test_fora_de_disparo_vai_para_o_proximo_do_mesmo_dia():
    assert proximo_horario_valido(_br(2026, 11, 5, 6, 0)) == _br(2026, 11, 5, 7, 30)
    assert proximo_horario_valido(_br(2026, 11, 5, 9, 0)) == _br(2026, 11, 5, 11, 30)
    assert proximo_horario_valido(_br(2026, 11, 5, 13, 0)) == _br(2026, 11, 5, 15, 0)


def test_depois_do_ultimo_disparo_vai_para_as_7h30_do_dia_seguinte():
    assert proximo_horario_valido(_br(2026, 11, 5, 16, 0)) == _br(2026, 11, 6, 7, 30)
    assert proximo_horario_valido(_br(2026, 11, 5, 23, 0)) == _br(2026, 11, 6, 7, 30)


def test_sabado_a_noite_e_domingo_vao_para_segunda():
    assert proximo_horario_valido(_br(2026, 11, 7, 20, 0)) == _br(2026, 11, 9, 7, 30)
    assert proximo_horario_valido(_br(2026, 11, 8, 9, 0)) == _br(2026, 11, 9, 7, 30)


def test_feriado_vai_para_o_proximo_dia_de_envio():
    # 15/11/2026 é domingo e feriado; 16/11 é segunda.
    assert proximo_horario_valido(_br(2026, 11, 15, 10, 0)) == _br(2026, 11, 16, 7, 30)
    # Sexta-feira Santa (3/4/2026): sábado 4/4 tem envio.
    assert proximo_horario_valido(_br(2026, 4, 3, 10, 0)) == _br(2026, 4, 4, 7, 30)
    # 20/11/2026 (sexta, feriado): sábado 21 tem envio.
    assert proximo_horario_valido(_br(2026, 11, 20, 9, 0)) == _br(2026, 11, 21, 7, 30)
    # 1/1/2027 é sexta (feriado); sábado 2 tem envio.
    assert proximo_horario_valido(_br(2027, 1, 1, 9, 0)) == _br(2027, 1, 2, 7, 30)


def test_converte_utc_para_o_horario_de_brasilia():
    # 10h UTC = 7h em Brasília (sem horário de verão desde 2019): ainda fechado; o disparo abre às 7:30.
    momento = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)
    assert not dentro_da_janela(momento)
    assert proximo_horario_valido(momento) == _br(2026, 11, 5, 7, 30)
    assert dentro_da_janela(datetime(2026, 11, 5, 10, 45, tzinfo=timezone.utc))  # 7:45 em Brasília


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
