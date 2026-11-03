"""Leitura dos formulários do Portal do Locatário."""

import pytest

from src.domain import formulario_portal as f
from src.domain.formulario_moto import ErroDeCampos

CONTRATO = {"km_atual": 12000, "ultima_km": 11000, "intervalo_km": 1500}
JPG = b"\xff\xd8\xff\xe0" + b"0" * 12
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
BOM = {"foto": ("painel.jpg", 5000, JPG), "nota": ("nota.png", 6000, PNG)}


def _ler(km="12.300", arquivos=None, multa="50.00"):
    return f.ler_troca_oleo({"km": km}, CONTRATO, BOM if arquivos is None else arquivos, multa)


def test_le_o_hodometro_com_ponto_de_milhar():
    assert _ler("12.300") == 12300 and _ler(" 12500 ") == 12500 and _ler("12000") == 12000


@pytest.mark.parametrize("km,trecho", [("", "apenas com números"), ("abc", "apenas com números"), ("11.999", "não pode ser menor")])
def test_km_invalido_ou_menor_que_o_registrado(km, trecho):
    with pytest.raises(ErroDeCampos) as erro:
        _ler(km)
    assert trecho in erro.value.erros["km"] and set(erro.value.erros) == {"km"}


def test_km_acima_do_intervalo_nao_e_erro_a_multa_e_decidida_depois():
    assert _ler("99.999") == 99999


def test_fotos_ausentes_citam_cada_campo():
    with pytest.raises(ErroDeCampos) as erro:
        _ler(arquivos={"foto": None})
    assert "anexe a foto mostrando o hodômetro" in erro.value.erros["foto"]
    assert "anexe a foto do óleo" in erro.value.erros["nota"]


@pytest.mark.parametrize("arquivo,trecho", [
    (("a.gif", 10, b"GIF89a"), "Extensão não permitida"),
    (("a.jpg", 10, PNG), "não corresponde"),
    (("a.jpg", 11 * 1024 * 1024, JPG), "mais de 10 MB"),
    (("a.jpg", 0, b""), "vazio"),
    (("a.pdf", 10, b"%PDF-1.7"), "Extensão não permitida"),
])
def test_foto_invalida_cita_o_campo(arquivo, trecho):
    with pytest.raises(ErroDeCampos) as erro:
        _ler(arquivos={"foto": arquivo, "nota": BOM["nota"]})
    assert trecho in erro.value.erros["foto"] and "nota" not in erro.value.erros


def test_todos_os_erros_vem_juntos():
    with pytest.raises(ErroDeCampos) as erro:
        _ler("x", arquivos={})
    assert set(erro.value.erros) == {"km", "foto", "nota"}


def test_texto_da_troca_guarda_so_o_km():
    assert f.texto_da_troca({"km": " 12.000 ", "foto": "x"}) == {"km": "12.000"}


def test_nova_senha_valida_e_erros_no_campo_certo():
    assert f.ler_nova_senha("abc12345", "abc12345", "529.982.247-25") == "abc12345"
    casos = [
        (("abc12345", "outra1234"), "confirmacao", "não conferem"),
        (("abc12", "abc12"), "nova", "pelo menos 8"),
        (("12345678", "12345678"), "nova", "só números"),
        (("cpf52998224725x", "cpf52998224725x"), "nova", "seu CPF"),
    ]
    for (nova, conf), campo, trecho in casos:
        with pytest.raises(ErroDeCampos) as erro:
            f.ler_nova_senha(nova, conf, "529.982.247-25")
        assert set(erro.value.erros) == {campo} and trecho in erro.value.erros[campo]
