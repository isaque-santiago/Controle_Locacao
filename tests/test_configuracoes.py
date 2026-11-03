"""Regras da tela Configurações: validação e exemplo de encargos."""

from decimal import Decimal

import pytest

from src.domain.configuracoes import exemplo_encargos, validar_configuracao

ENTRADA = {
    "multa_atraso_valor": "15,00",
    "encargo_diario_valor": "7,00",
    "alerta_manutencao_km": 300,
    "alerta_manutencao_dias": 15,
    "alerta_documento_dias": 30,
    "alerta_cnh_dias": 30,
    "multa_troca_oleo_valor": "0,00",
}


def test_validar_converte_encargos_em_reais_e_inteiros():
    dados = validar_configuracao(ENTRADA)
    assert dados["multa_atraso_valor"] == "15.00"
    assert dados["encargo_diario_valor"] == "7.00"
    assert dados["alerta_manutencao_km"] == 300
    assert "carencia_dias" not in dados


def test_validar_converte_encargos_com_milhar_e_simbolo():
    dados = validar_configuracao({**ENTRADA, "multa_atraso_valor": "R$ 1.250,50", "encargo_diario_valor": "7,5"})
    assert dados["multa_atraso_valor"] == "1250.50"
    assert dados["encargo_diario_valor"] == "7.50"


def test_validar_converte_multa_fixa_de_troca_de_oleo():
    dados = validar_configuracao({**ENTRADA, "multa_troca_oleo_valor": "R$ 1.250,50"})
    assert dados["multa_troca_oleo_valor"] == "1250.50"


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("multa_atraso_valor", "abc"),
        ("multa_atraso_valor", "-1"),
        ("multa_atraso_valor", ""),
        ("encargo_diario_valor", "7,999"),
        ("encargo_diario_valor", "-0,01"),
        ("alerta_manutencao_dias", "-3"),
        ("alerta_manutencao_dias", "2,5"),
        ("alerta_cnh_dias", ""),
        ("alerta_manutencao_km", "999999999"),
        ("multa_troca_oleo_valor", "abc"),
        ("multa_troca_oleo_valor", "-5"),
        ("multa_troca_oleo_valor", "10,999"),
    ],
)
def test_validar_rejeita_valores_invalidos(campo, valor):
    with pytest.raises(ValueError):
        validar_configuracao({**ENTRADA, campo: valor})


def test_exemplo_encargos_com_valores_padrao():
    # locação de R$ 500, vencida há 5 dias: 15 + 7 * 5 = 50
    exemplo = exemplo_encargos(Decimal("15.00"), Decimal("7.00"))
    assert exemplo["multa"] == Decimal("15.00")
    assert exemplo["adicional_diario"] == Decimal("35.00")
    assert exemplo["total"] == Decimal("550.00")


def test_exemplo_encargos_usa_os_valores_informados():
    exemplo = exemplo_encargos(Decimal("20.00"), Decimal("5.00"), dias_vencida=2)
    assert exemplo["encargos"] == Decimal("30.00")
    assert exemplo["total"] == Decimal("530.00")


DO_BANCO = {
    **ENTRADA,
    "multa_atraso_valor": Decimal("15.00"),
    "encargo_diario_valor": Decimal("7.00"),
    "multa_troca_oleo_valor": Decimal("0.00"),
}
