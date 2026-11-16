"""Testes de src/domain/sessao_longa.py (duração da sessão)."""

from src.domain.sessao_longa import (
    INATIVIDADE_MAXIMA_SEGUNDOS,
    UM_DIA_SEGUNDOS,
    VIDA_MAXIMA_SEGUNDOS,
    limite_do_aviso,
    sessao_vencida,
)


def test_politica_de_90_dias_de_inatividade_e_1_ano_de_vida():
    assert INATIVIDADE_MAXIMA_SEGUNDOS == 90 * UM_DIA_SEGUNDOS
    assert VIDA_MAXIMA_SEGUNDOS == 365 * UM_DIA_SEGUNDOS


class TestSessaoVencida:
    def test_dentro_dos_prazos(self):
        assert not sessao_vencida(criada_em=1000, ultima_atividade=1000 + 89 * UM_DIA_SEGUNDOS, agora=1000 + 89 * UM_DIA_SEGUNDOS)

    def test_vence_por_inatividade_de_mais_de_90_dias(self):
        assert sessao_vencida(1000, 1000, 1000 + INATIVIDADE_MAXIMA_SEGUNDOS + 1)
        assert not sessao_vencida(1000, 1000, 1000 + INATIVIDADE_MAXIMA_SEGUNDOS)

    def test_uso_continuo_vence_pela_vida_maxima(self):
        agora = 1000 + VIDA_MAXIMA_SEGUNDOS + 1
        assert sessao_vencida(1000, agora - 60, agora)

    def test_criada_em_desconhecida_so_vale_a_inatividade(self):
        agora = 10 * VIDA_MAXIMA_SEGUNDOS
        assert not sessao_vencida(0, agora - 60, agora)
        assert sessao_vencida(0, agora - INATIVIDADE_MAXIMA_SEGUNDOS - 1, agora)

    def test_limites_personalizados(self):
        assert sessao_vencida(1000, 1000, 1000 + 1801, limite_inatividade=1800)


class TestLimiteDoAviso:
    def test_prazo_curto_mantem_o_aviso(self):
        assert limite_do_aviso(1800) == 1800

    def test_prazo_longo_desliga_o_aviso(self):
        assert limite_do_aviso(INATIVIDADE_MAXIMA_SEGUNDOS) == 0
        assert limite_do_aviso(0) == 0
