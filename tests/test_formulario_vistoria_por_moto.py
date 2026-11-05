"""Formulário de vistoria com um bloco por moto vinculada: nomes com prefixo, leitura e erros."""

import pytest

from src.domain.formulario_contrato import PREFIXO_ITEM, vistoria_inicial
from src.domain.formulario_moto import ErroDeCampos
from src.domain.formulario_vistoria_por_moto import (
    com_prefixo,
    ler_vistorias_vinculadas,
    prefixo,
    sem_prefixo,
    texto_das_vinculadas,
    textos_iniciais,
)

MOTOS = [{"id": "m2", "km_atual": 500}, {"id": "m3", "km_atual": 80}]


def _bloco(n, moto_id, km):
    return com_prefixo({**vistoria_inicial(0), "km": str(km)}, prefixo(n)) | {prefixo(n) + "moto": moto_id}


def test_prefixo_da_primeira_e_da_segunda_vinculada():
    assert prefixo(1) == "vinc1_" and prefixo(2) == "vinc2_"


def test_com_e_sem_prefixo_sao_inversos():
    assert sem_prefixo(com_prefixo({"km": "1", "avarias": "x"}, "vinc1_"), "vinc1_") == {"km": "1", "avarias": "x"}
    assert sem_prefixo({"km": "1", "vinc1_km": "2"}, "vinc1_") == {"km": "2"}


def test_textos_iniciais_trazem_o_km_de_cada_moto():
    texto = textos_iniciais(MOTOS)
    assert texto["vinc1_km"] == "500" and texto["vinc2_km"] == "80"
    assert texto["vinc1_" + PREFIXO_ITEM + "farol_dianteiro"] == "ok"


def test_texto_das_vinculadas_guarda_o_que_foi_digitado():
    entrada = _bloco(1, "m2", "abc") | _bloco(2, "m3", 90)
    texto = texto_das_vinculadas(entrada, MOTOS)
    assert texto["vinc1_km"] == "abc" and texto["vinc2_km"] == "90"


def test_le_a_vistoria_de_cada_vinculada_na_ordem():
    entrada = _bloco(1, "m2", 520) | _bloco(2, "m3", 90)
    lidas = ler_vistorias_vinculadas(entrada, MOTOS)
    assert [(v["moto_id"], v["km"]) for v in lidas] == [("m2", 520), ("m3", 90)]
    assert lidas[0]["checklist"]["farol_dianteiro"] == "ok"


def test_km_menor_que_o_atual_da_moto_aponta_o_campo_prefixado():
    entrada = _bloco(1, "m2", 10) | _bloco(2, "m3", 90)
    with pytest.raises(ErroDeCampos) as erro:
        ler_vistorias_vinculadas(entrada, MOTOS)
    assert set(erro.value.erros) == {"vinc1_km"}


def test_junta_os_erros_de_todas_as_vinculadas():
    entrada = _bloco(1, "m2", "x") | _bloco(2, "m3", "y")
    with pytest.raises(ErroDeCampos) as erro:
        ler_vistorias_vinculadas(entrada, MOTOS)
    assert {"vinc1_km", "vinc2_km"} <= set(erro.value.erros)


def test_recusa_quando_a_lista_de_motos_mudou():
    entrada = _bloco(1, "m9", 520) | _bloco(2, "m3", 90)
    with pytest.raises(ErroDeCampos) as erro:
        ler_vistorias_vinculadas(entrada, MOTOS)
    assert "mudou" in erro.value.erros["vinc1_km"]


def test_sem_vinculadas_devolve_lista_vazia():
    assert ler_vistorias_vinculadas({}, []) == []
