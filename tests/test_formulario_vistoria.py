"""Leitura do registro de vistoria e validação das fotos."""

from datetime import date

import pytest

from src.domain import formulario_vistoria as f
from src.domain.formulario_moto import ErroDeCampos
from src.domain.vistorias import CHECKLIST_PADRAO

HOJE = date(2026, 10, 8)


def _entrada(**extra):
    base = {"tipo": "entrega", "data": "2026-10-01", "km": "12.000", "nivel_combustivel": "cheio", "avarias": "",
            "adicionais": "", **{"item_" + i: "ok" for i in CHECKLIST_PADRAO}}
    return {**base, **extra}


def _ler(**extra):
    return f.ler_registro(_entrada(**extra), HOJE, "2026-08-01", 12000, ["entrega", "devolucao"])


def test_inicial_usa_primeiro_tipo_que_falta_hoje_e_combustivel_cheio():
    v = f.registro_inicial(HOJE, 12000, ["devolucao"])
    assert v["tipo"] == "devolucao" and v["data"] == "2026-10-08" and v["km"] == "12000"
    assert v["nivel_combustivel"] == "cheio" and v["item_buzina"] == "ok"


def test_le_registro_valido_com_adicionais_e_avarias_vazia_vira_none():
    dados = _ler(adicionais="capa de chuva=ok", avarias="  ")
    assert dados["tipo"] == "entrega" and dados["dia"] == date(2026, 10, 1)
    assert dados["vistoria"]["km"] == 12000 and dados["vistoria"]["avarias"] is None
    assert dados["vistoria"]["checklist"]["capa de chuva"] == "ok"
    assert _ler(avarias=" risco ")["vistoria"]["avarias"] == "risco"


@pytest.mark.parametrize("extra,campo", [
    ({"tipo": "devolucao"}, None),
    ({"tipo": "x"}, "tipo"),
    ({"data": ""}, "data"),
    ({"data": "2026-10-09"}, "data"),
    ({"data": "2026-07-31"}, "data"),
    ({"data": "abc"}, "data"),
    ({"km": "11999"}, "km"),
    ({"nivel_combustivel": "x"}, "nivel_combustivel"),
    ({"adicionais": "sem estado"}, "adicionais"),
    ({"item_buzina": ""}, "item_buzina"),
])
def test_valida_campo_a_campo(extra, campo):
    if campo is None:
        assert _ler(**extra)["tipo"] == "devolucao"
        return
    with pytest.raises(ErroDeCampos) as erro:
        _ler(**extra)
    assert campo in erro.value.erros


def test_tipo_ja_registrado_nao_e_aceito():
    with pytest.raises(ErroDeCampos) as erro:
        f.ler_registro(_entrada(), HOJE, "2026-08-01", 12000, ["devolucao"])
    assert "tipo" in erro.value.erros


def test_mensagem_de_data_antes_do_inicio_cita_a_data_do_contrato():
    with pytest.raises(ErroDeCampos) as erro:
        _ler(data="2026-07-31")
    assert "01/08/2026" in erro.value.erros["data"]


JPG = b"\xff\xd8\xff\xe0" + b"0" * 12


def test_fotos_validas_e_sem_fotos_passam():
    f.validar_fotos([])
    f.validar_fotos([("a.jpg", 1000, JPG), ("b.PNG", 5, b"\x89PNG\r\n\x1a\n")])


@pytest.mark.parametrize("fotos,trecho", [
    ([("a.jpg", 1000, JPG)] * 11, "até 10"),
    ([("a.jpg", 11 * 1024 * 1024, JPG)], "mais de 10 MB"),
    ([("a.gif", 10, b"GIF89a")], "Extensão não permitida"),
    ([("a.png", 10, JPG)], "não corresponde"),
    ([("a.jpg", 0, b"")], "vazio"),
])
def test_fotos_invalidas_citam_o_arquivo(fotos, trecho):
    with pytest.raises(ErroDeCampos) as erro:
        f.validar_fotos(fotos)
    assert trecho in erro.value.erros["fotos"]
