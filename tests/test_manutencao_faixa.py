"""Faixa de km nos itens de manutenção (seção 14.5): alerta no mínimo, vencida no máximo."""

from datetime import date
from unittest.mock import patch

import pytest

from src.domain.manutencao_regras import (
    calcular_inicio_alerta_km,
    calcular_proxima_manutencao,
    calcular_situacao,
)
from src.services import manutencao

HOJE = date(2026, 10, 5)


class TestInicioAlertaKm:
    def test_soma_o_minimo_a_ultima_km(self):
        assert calcular_inicio_alerta_km(10_000, 3000, 5000) == 13_000

    def test_sem_ultima_km_conta_a_partir_de_zero(self):
        assert calcular_inicio_alerta_km(None, 3000, 5000) == 3000

    def test_sem_minimo_ou_sem_maximo_nao_ha_faixa(self):
        assert calcular_inicio_alerta_km(10_000, None, 5000) is None
        assert calcular_inicio_alerta_km(10_000, 3000, None) is None

    @pytest.mark.parametrize("minimo", [5000, 6000])
    def test_minimo_nao_pode_alcancar_o_maximo(self, minimo):
        with pytest.raises(ValueError):
            calcular_inicio_alerta_km(0, minimo, 5000)


def _situacao(km_atual, ultima_km=10_000, minimo=3000, maximo=5000):
    proxima = calcular_proxima_manutencao(ultima_km, maximo, None, None)
    return calcular_situacao(
        km_atual,
        proxima["proxima_km"],
        HOJE,
        None,
        alerta_km=300,
        alerta_dias=15,
        alerta_inicio_km=calcular_inicio_alerta_km(ultima_km, minimo, maximo),
    )


class TestSituacaoComFaixa:
    """Kit de tração: última troca em 10.000 km, faixa de 3.000 a 5.000 km."""

    def test_antes_do_minimo_esta_em_dia(self):
        assert _situacao(12_999) == "em_dia"

    def test_no_minimo_o_alerta_comeca(self):
        assert _situacao(13_000) == "proxima"

    def test_dentro_da_faixa_continua_proxima(self):
        assert _situacao(14_000) == "proxima"
        assert _situacao(14_699) == "proxima"

    def test_no_maximo_vence(self):
        assert _situacao(15_000) == "vencida"
        assert _situacao(15_200) == "vencida"

    def test_sem_faixa_vale_a_antecedencia_global(self):
        # óleo: 1.000 km, sem mínimo -> alerta 300 km antes (a partir de 700 km rodados)
        assert _situacao(10_699, minimo=None, maximo=1000) == "em_dia"
        assert _situacao(10_700, minimo=None, maximo=1000) == "proxima"
        assert _situacao(11_000, minimo=None, maximo=1000) == "vencida"

    def test_sem_alerta_inicio_o_comportamento_antigo_nao_muda(self):
        assert calcular_situacao(4000, 6000, HOJE, None, 300, 15) == "em_dia"


def _linha(minimo_linha=None, minimo_item=3000, km_linha=None, km_item=5000, ultima_km=10_000):
    return {
        "ultima_km": ultima_km,
        "ultima_data": None,
        "intervalo_km": km_linha,
        "intervalo_dias": None,
        "intervalo_minimo_km": minimo_linha,
        "item": {
            "nome": "Kit de tração",
            "intervalo_km": km_item,
            "intervalo_dias": None,
            "intervalo_minimo_km": minimo_item,
        },
    }


def _plano(linha):
    config = {"alerta_manutencao_km": 300, "alerta_manutencao_dias": 15}
    with (
        patch("src.services.manutencao.configuracoes.obter", return_value=config),
        patch("src.services.manutencao.moto_plano_manutencao.listar_por_moto", return_value=[linha]),
        patch("src.services.manutencao.hoje_br", return_value=HOJE),
    ):
        return manutencao.listar_plano_moto("m")[0]


class TestPlanoDaMoto:
    def test_usa_a_faixa_do_catalogo(self):
        item = _plano(_linha())
        assert item["intervalo_minimo_km_efetivo"] == 3000
        assert item["alerta_inicio_km"] == 13_000
        assert item["proxima_km"] == 15_000
        assert manutencao.situacao_item_plano(item, 12_000) == "em_dia"
        assert manutencao.situacao_item_plano(item, 13_500) == "proxima"
        assert manutencao.situacao_item_plano(item, 15_000) == "vencida"

    def test_sobrescrita_da_moto_prevalece_sobre_o_catalogo(self):
        item = _plano(_linha(minimo_linha=2000, km_linha=4000))
        assert item["alerta_inicio_km"] == 12_000
        assert item["proxima_km"] == 14_000

    def test_sobrescrita_que_torna_a_faixa_incoerente_volta_ao_alerta_global(self):
        # moto com intervalo 2.500 km mas catálogo com mínimo 3.000 km: o mínimo não vale
        item = _plano(_linha(km_linha=2500))
        assert item["intervalo_minimo_km_efetivo"] is None
        assert item["alerta_inicio_km"] is None
        assert manutencao.situacao_item_plano(item, 12_100) == "em_dia"
        assert manutencao.situacao_item_plano(item, 12_300) == "proxima"

    def test_item_sem_faixa_nao_tem_inicio_de_alerta(self):
        item = _plano(_linha(minimo_item=None, km_item=1000))
        assert item["alerta_inicio_km"] is None


class TestCatalogo:
    def test_aceita_faixa_valida(self):
        with patch("src.services.manutencao.itens_manutencao.criar", return_value={}) as criar:
            manutencao.criar_item_catalogo(
                {"nome": "Patins", "intervalo_km": 5000, "intervalo_minimo_km": 3000, "intervalo_dias": None}
            )
        criar.assert_called_once()

    @pytest.mark.parametrize(
        "dados",
        [
            {"intervalo_km": 5000, "intervalo_minimo_km": 5000},
            {"intervalo_km": 5000, "intervalo_minimo_km": 7000},
            {"intervalo_km": None, "intervalo_dias": 90, "intervalo_minimo_km": 100},
        ],
    )
    def test_recusa_faixa_invalida(self, dados):
        with patch("src.services.manutencao.itens_manutencao.criar") as criar:
            with pytest.raises(ValueError, match="Alerta a partir de"):
                manutencao.criar_item_catalogo({"nome": "X", **dados})
        criar.assert_not_called()

    def test_atualizar_tambem_valida_a_faixa(self):
        with patch("src.services.manutencao.itens_manutencao.atualizar") as atualizar:
            with pytest.raises(ValueError):
                manutencao.atualizar_item_catalogo("i", {"intervalo_km": 1000, "intervalo_minimo_km": 2000})
        atualizar.assert_not_called()
