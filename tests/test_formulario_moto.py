"""Leitura e validação dos formulários de moto (src/domain/formulario_moto.py)."""

from datetime import date

import pytest

from src.domain.formulario_moto import ErroDeCampos, ler_km, ler_moto, ler_regularizacao

VALIDA = {
    "placa": "abc-1d23",
    "marca": " Honda ",
    "modelo": "CG 160",
    "renavam": "",
    "chassi": " 9C2 ",
    "cor": "",
    "ano_fabricacao": "2023",
    "ano_modelo": "2024",
    "km_atual": "1.250",
    "valor_aquisicao": "12.500,00",
    "valor_locacao_sugerido": "320,5",
    "data_aquisicao": "2026-03-01",
    "observacoes": "  ",
}


def test_cadastro_valido_normaliza_os_dados():
    dados = ler_moto(VALIDA, nova=True)
    assert dados["placa"] == "ABC1D23"
    assert dados["marca"] == "Honda" and dados["chassi"] == "9C2"
    assert dados["renavam"] is None and dados["cor"] is None and dados["observacoes"] is None
    assert dados["ano_fabricacao"] == 2023 and dados["ano_modelo"] == 2024
    assert dados["km_atual"] == 1250
    assert dados["valor_aquisicao"] == "12500.00" and dados["valor_locacao_sugerido"] == "320.50"
    assert dados["data_aquisicao"] == "2026-03-01"


def test_edicao_nao_leva_km_atual():
    assert "km_atual" not in ler_moto(VALIDA, nova=False)


def test_dinheiro_nunca_vira_float():
    dados = ler_moto({**VALIDA, "valor_locacao_sugerido": "0,10"}, nova=True)
    assert isinstance(dados["valor_locacao_sugerido"], str) and dados["valor_locacao_sugerido"] == "0.10"


def test_campos_vazios_obrigatorios_geram_um_erro_por_campo():
    with pytest.raises(ErroDeCampos) as erro:
        ler_moto({}, nova=True)
    assert set(erro.value.erros) >= {"placa", "marca", "modelo", "ano_fabricacao", "ano_modelo", "valor_aquisicao", "valor_locacao_sugerido"}
    assert "km_atual" not in erro.value.erros  # vazio vale 0 no cadastro


@pytest.mark.parametrize("placa", ["ABC12", "1234567", "AB-1234", "ABC 1D23X"])
def test_placa_invalida(placa):
    with pytest.raises(ErroDeCampos) as erro:
        ler_moto({**VALIDA, "placa": placa}, nova=True)
    assert erro.value.erros["placa"] == "Placa: use ABC1234 ou ABC1D23."


def test_placa_antiga_e_mercosul_valem():
    assert ler_moto({**VALIDA, "placa": "ABC-1234"}, nova=True)["placa"] == "ABC1234"
    assert ler_moto({**VALIDA, "placa": "abc1d23"}, nova=True)["placa"] == "ABC1D23"


def test_anos_fora_do_intervalo_e_texto():
    with pytest.raises(ErroDeCampos) as erro:
        ler_moto({**VALIDA, "ano_fabricacao": "1800", "ano_modelo": "vinte"}, nova=True)
    assert "Ano de fabricação" in erro.value.erros["ano_fabricacao"]
    assert "Ano do modelo" in erro.value.erros["ano_modelo"]


def test_valor_negativo_ou_mal_formatado():
    with pytest.raises(ErroDeCampos) as erro:
        ler_moto({**VALIDA, "valor_aquisicao": "-5", "valor_locacao_sugerido": "1,234,5"}, nova=True)
    assert "negativo" in erro.value.erros["valor_aquisicao"]
    assert "valor_locacao_sugerido" in erro.value.erros


def test_data_invalida_e_data_vazia():
    with pytest.raises(ErroDeCampos) as erro:
        ler_moto({**VALIDA, "data_aquisicao": "31/02/2026"}, nova=True)
    assert "data_aquisicao" in erro.value.erros
    assert ler_moto({**VALIDA, "data_aquisicao": ""}, nova=True)["data_aquisicao"] is None


def test_km_com_milhar_e_confirmacao():
    assert ler_km({"km": "12.345"}) == (12345, False)
    assert ler_km({"km": "10", "confirmar_km_menor": "on"}) == (10, True)


@pytest.mark.parametrize("valor", ["", "abc", "-3", "1,5"])
def test_km_invalido(valor):
    with pytest.raises(ErroDeCampos) as erro:
        ler_km({"km": valor})
    assert "Nova leitura" in erro.value.erros["km"]


def test_data_de_regularizacao():
    assert ler_regularizacao({"data": "2026-10-06"}) == date(2026, 10, 6)
    for ruim in ("", "ontem", "2026-13-01"):
        with pytest.raises(ErroDeCampos):
            ler_regularizacao({"data": ruim})
