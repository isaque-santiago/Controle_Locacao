"""Leitura do formulário de Configurações."""

from decimal import Decimal

import pytest

from src.domain import formulario_configuracao as f
from src.domain.configuracoes import validar_configuracao
from src.domain.formulario_moto import ErroDeCampos

CONFIG = {
    "multa_atraso_valor": Decimal("15.00"), "encargo_diario_valor": Decimal("7"), "multa_troca_oleo_valor": None,
    "alerta_manutencao_km": 300, "alerta_manutencao_dias": 15, "alerta_documento_dias": 30, "alerta_cnh_dias": 0,
}


def _entrada(**extra):
    return {**f.valores_iniciais(CONFIG), **extra}


def test_valores_iniciais_formatam_o_que_esta_salvo():
    v = f.valores_iniciais(CONFIG)
    assert v["multa_atraso_valor"] == "15,00" and v["encargo_diario_valor"] == "7,00" and v["multa_troca_oleo_valor"] == "0,00"
    assert v["alerta_manutencao_km"] == "300" and v["alerta_cnh_dias"] == "0"


def test_le_valores_validos_e_o_servico_aceita():
    dados = f.ler_configuracao(_entrada(multa_atraso_valor="R$ 1.250,50", encargo_diario_valor="7,5", alerta_manutencao_km="1000"))
    assert dados["multa_atraso_valor"] == Decimal("1250.50") and dados["encargo_diario_valor"] == Decimal("7.50")
    assert dados["alerta_manutencao_km"] == 1000 and dados["alerta_cnh_dias"] == 0
    assert validar_configuracao(dados)["multa_atraso_valor"] == "1250.50"  # o serviço revalida sem estranhar o Decimal


@pytest.mark.parametrize("extra,campo", [
    ({"multa_atraso_valor": ""}, "multa_atraso_valor"), ({"encargo_diario_valor": "abc"}, "encargo_diario_valor"),
    ({"multa_troca_oleo_valor": "-1"}, "multa_troca_oleo_valor"), ({"multa_atraso_valor": "1,234"}, "multa_atraso_valor"),
    ({"alerta_manutencao_km": "-5"}, "alerta_manutencao_km"), ({"alerta_manutencao_dias": "1,5"}, "alerta_manutencao_dias"),
    ({"alerta_documento_dias": ""}, "alerta_documento_dias"), ({"alerta_cnh_dias": "100001"}, "alerta_cnh_dias"),
])
def test_valida_campo_a_campo(extra, campo):
    with pytest.raises(ErroDeCampos) as erro:
        f.ler_configuracao(_entrada(**extra))
    assert campo in erro.value.erros


def test_varios_erros_vem_juntos_e_limites_valem():
    with pytest.raises(ErroDeCampos) as erro:
        f.ler_configuracao(_entrada(multa_atraso_valor="x", alerta_cnh_dias="y"))
    assert set(erro.value.erros) == {"multa_atraso_valor", "alerta_cnh_dias"}
    assert f.ler_configuracao(_entrada(alerta_cnh_dias="100000"))["alerta_cnh_dias"] == 100000
    assert f.ler_configuracao(_entrada(multa_atraso_valor="0,00"))["multa_atraso_valor"] == Decimal("0.00")
