"""Testes de src/domain/manutencao_regras.py (Fase 3)."""

from datetime import date

from src.domain.manutencao_regras import calcular_proxima_manutencao, calcular_situacao

_ALERTA_KM = 300
_ALERTA_DIAS = 15


class TestCalcularProximaManutencao:
    def test_so_intervalo_km(self):
        resultado = calcular_proxima_manutencao(
            ultima_km=5000, intervalo_km=1000, ultima_data=None, intervalo_dias=None
        )
        assert resultado == {"proxima_km": 6000, "proxima_data": None}

    def test_so_intervalo_dias(self):
        resultado = calcular_proxima_manutencao(
            ultima_km=None,
            intervalo_km=None,
            ultima_data=date(2026, 1, 1),
            intervalo_dias=365,
        )
        assert resultado == {"proxima_km": None, "proxima_data": date(2027, 1, 1)}

    def test_km_e_dias_juntos(self):
        resultado = calcular_proxima_manutencao(
            ultima_km=5000,
            intervalo_km=1000,
            ultima_data=date(2026, 1, 1),
            intervalo_dias=90,
        )
        assert resultado == {"proxima_km": 6000, "proxima_data": date(2026, 4, 1)}

    def test_sem_ultima_km_considera_zero(self):
        resultado = calcular_proxima_manutencao(
            ultima_km=None, intervalo_km=1000, ultima_data=None, intervalo_dias=None
        )
        assert resultado["proxima_km"] == 1000

    def test_intervalo_dias_sem_ultima_data_nao_calcula(self):
        resultado = calcular_proxima_manutencao(
            ultima_km=None, intervalo_km=None, ultima_data=None, intervalo_dias=90
        )
        assert resultado["proxima_data"] is None


class TestCalcularSituacao:
    def test_em_dia_por_km(self):
        situacao = calcular_situacao(
            km_atual=4000,
            proxima_km=6000,
            hoje=date(2026, 1, 1),
            proxima_data=None,
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "em_dia"

    def test_proxima_por_km_dentro_do_limite(self):
        situacao = calcular_situacao(
            km_atual=5800,
            proxima_km=6000,
            hoje=date(2026, 1, 1),
            proxima_data=None,
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "proxima"

    def test_vencida_por_km_ja_passou(self):
        situacao = calcular_situacao(
            km_atual=6000,
            proxima_km=6000,
            hoje=date(2026, 1, 1),
            proxima_data=None,
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "vencida"

    def test_proxima_por_data_dentro_do_limite(self):
        situacao = calcular_situacao(
            km_atual=1000,
            proxima_km=None,
            hoje=date(2026, 3, 20),
            proxima_data=date(2026, 4, 1),
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "proxima"

    def test_vencida_por_data_ja_passou(self):
        situacao = calcular_situacao(
            km_atual=1000,
            proxima_km=None,
            hoje=date(2026, 4, 2),
            proxima_data=date(2026, 4, 1),
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "vencida"

    def test_vence_o_que_chegar_primeiro_km_vencida_mesmo_com_data_em_dia(self):
        situacao = calcular_situacao(
            km_atual=6000,
            proxima_km=6000,
            hoje=date(2026, 1, 1),
            proxima_data=date(2027, 1, 1),
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "vencida"

    def test_sem_intervalo_nenhum_fica_em_dia(self):
        situacao = calcular_situacao(
            km_atual=1000,
            proxima_km=None,
            hoje=date(2026, 1, 1),
            proxima_data=None,
            alerta_km=_ALERTA_KM,
            alerta_dias=_ALERTA_DIAS,
        )
        assert situacao == "em_dia"
