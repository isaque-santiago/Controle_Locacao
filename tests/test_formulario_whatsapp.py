"""Testes de src/domain/formulario_whatsapp.py: controles do envio em Configurações."""

import pytest

from src.domain.formulario_moto import ErroDeCampos
from src.domain.formulario_whatsapp import ler_whatsapp, texto_da_entrada, valores_iniciais


def test_valores_iniciais_do_banco():
    v = valores_iniciais({"whatsapp_ativo": False, "whatsapp_modo_teste": True, "whatsapp_numero_teste": None, "whatsapp_max_repeticoes": 10})
    assert v == {"ativo": False, "modo": "teste", "numero_teste": "", "max_repeticoes": "10", "confirmo": False}
    v = valores_iniciais({"whatsapp_ativo": True, "whatsapp_modo_teste": False, "whatsapp_numero_teste": "5511988887777", "whatsapp_max_repeticoes": 5})
    assert v["ativo"] is True and v["modo"] == "real" and v["numero_teste"] == "(11) 98888-7777" and v["max_repeticoes"] == "5"


def test_banco_antigo_sem_as_colunas_fica_desligado_em_modo_teste():
    v = valores_iniciais({})
    assert v["ativo"] is False and v["modo"] == "teste" and v["max_repeticoes"] == "10"


def test_desligado_grava_sem_exigir_numero():
    assert ler_whatsapp({"modo": "teste", "numero_teste": "", "max_repeticoes": "10"}) == {
        "whatsapp_ativo": False, "whatsapp_modo_teste": True, "whatsapp_numero_teste": None, "whatsapp_max_repeticoes": 10}


def test_modo_teste_ligado_exige_o_numero_de_teste():
    with pytest.raises(ErroDeCampos) as erro:
        ler_whatsapp({"ativo": "on", "modo": "teste", "numero_teste": "", "max_repeticoes": "10"})
    assert "Número de teste: informe o seu celular" in erro.value.erros["numero_teste"]


def test_numero_de_teste_e_normalizado():
    dados = ler_whatsapp({"ativo": "on", "modo": "teste", "numero_teste": "(11) 98888-7777", "max_repeticoes": "10"})
    assert dados["whatsapp_numero_teste"] == "5511988887777" and dados["whatsapp_ativo"] and dados["whatsapp_modo_teste"]


def test_numero_de_teste_invalido():
    with pytest.raises(ErroDeCampos) as erro:
        ler_whatsapp({"modo": "teste", "numero_teste": "123", "max_repeticoes": "10"})
    assert "por exemplo (11) 98888-7777" in erro.value.erros["numero_teste"]


def test_sair_do_modo_teste_exige_confirmacao():
    with pytest.raises(ErroDeCampos) as erro:
        ler_whatsapp({"ativo": "on", "modo": "real", "max_repeticoes": "10"})
    assert "vão para os clientes" in erro.value.erros["confirmo"]
    dados = ler_whatsapp({"ativo": "on", "modo": "real", "confirmo": "on", "max_repeticoes": "10"})
    assert dados["whatsapp_ativo"] is True and dados["whatsapp_modo_teste"] is False


def test_modo_real_desligado_nao_exige_confirmacao():
    assert ler_whatsapp({"modo": "real", "max_repeticoes": "10"})["whatsapp_modo_teste"] is False


@pytest.mark.parametrize("valor", ["0", "101", "abc", "", "-1", "2,5"])
def test_maximo_de_avisos_invalido(valor):
    with pytest.raises(ErroDeCampos) as erro:
        ler_whatsapp({"modo": "teste", "max_repeticoes": valor})
    assert "Máximo de avisos por assunto" in erro.value.erros["max_repeticoes"]


def test_texto_da_entrada_devolve_o_digitado():
    assert texto_da_entrada({"ativo": "on", "modo": "x", "numero_teste": " 11 9 ", "max_repeticoes": "7"}) == {
        "ativo": True, "modo": "teste", "numero_teste": "11 9", "max_repeticoes": "7", "confirmo": False}


def test_motivo_do_bloqueio():
    from src.domain.formulario_whatsapp import ler_bloqueio

    assert ler_bloqueio({"motivo": "  Pediu ao dono  "}) == "Pediu ao dono"
    for ruim in ("", "ab", "x" * 201):
        with pytest.raises(ErroDeCampos) as erro:
            ler_bloqueio({"motivo": ruim})
        assert "Motivo:" in erro.value.erros["motivo"]
