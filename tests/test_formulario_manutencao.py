"""Regras puras do formulário web de registro de manutenção."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.formulario_manutencao import (
    alterar_linhas,
    ler,
    ler_finalizacao,
    ler_item_catalogo,
    previa,
    valores_finalizacao,
    valores_iniciais,
    valores_item_catalogo,
)
from src.domain.formulario_moto import ErroDeCampos

MOTO = {"id": "m1", "km_atual": 1000}
CATALOGO = [{"id": "i1", "nome": "Óleo", "ativo": True}]


def _validos(**extra):
    return {**valores_iniciais(date(2026, 10, 7), MOTO), "descricao": "Revisão", **extra}


def test_le_dados_itens_do_plano_e_adicionais_com_decimal():
    dados = ler(_validos(item_i1="1", qtd_i1="2", valor_i1="35,90", extras_ids="0",
                        extra_descricao_0="Limpeza", extra_qtd_0="1", extra_valor_0="20,00"), MOTO, CATALOGO)
    assert dados["km"] == 1000 and dados["status"] == "concluida"
    assert dados["itens"] == [
        {"item_id": "i1", "descricao": "Óleo", "quantidade": Decimal("2"), "valor_unitario": Decimal("35.90")},
        {"descricao": "Limpeza", "quantidade": Decimal("1"), "valor_unitario": Decimal("20.00")},
    ]


def test_valida_campos_datas_km_e_linha_adicional():
    with pytest.raises(ErroDeCampos) as capturado:
        ler(_validos(data_entrada="2026-10-08", data_saida="2026-10-07", km="999", descricao="",
                     extras_ids="0", extra_qtd_0="2", extra_valor_0="10"), MOTO, CATALOGO)
    assert set(capturado.value.erros) >= {"data_saida", "km", "descricao", "extra_descricao_0"}


def test_status_aberto_ignora_data_de_saida():
    assert ler(_validos(status="aberta", data_saida="invalida"), MOTO, CATALOGO)["data_saida"] is None


def test_previa_e_linhas_dinamicas_sao_tolerantes():
    valores = alterar_linhas(_validos(), "adicionar")
    assert valores["extras_ids"] == "0"
    valores.update(item_i1="1", qtd_i1="2", valor_i1="10", extra_descricao_0="Peça",
                   extra_qtd_0="x", extra_valor_0="5", custo_mao_obra="30")
    assert previa(valores, CATALOGO)["total"] == Decimal("50.00")
    assert alterar_linhas(valores, "remover:0")["extras_ids"] == ""


def test_finalizacao_sugere_hoje_e_maior_km_e_valida_limites():
    manutencao = {"data_entrada": "2026-10-01", "km": 1200}
    moto = {"km_atual": 1500}
    assert valores_finalizacao(date(2026, 10, 7), manutencao, moto) == {
        "data": "2026-10-07", "km": "1500", "confirmar": False,
    }
    dados = ler_finalizacao({"data": "2026-10-07", "km": "1500"}, manutencao, moto, "concluida")
    assert dados == {"data": date(2026, 10, 7), "km": 1500, "status": "concluida"}
    with pytest.raises(ErroDeCampos) as capturado:
        ler_finalizacao({"data": "2026-09-30", "km": "1499"}, manutencao, moto, "concluida")
    assert set(capturado.value.erros) == {"data", "km"}


def test_cancelamento_exige_confirmacao():
    manutencao = {"data_entrada": "2026-10-01", "km": 1200}
    moto = {"km_atual": 1500}
    with pytest.raises(ErroDeCampos) as capturado:
        ler_finalizacao({"data": "2026-10-07", "km": "1500"}, manutencao, moto, "cancelada")
    assert "confirmar" in capturado.value.erros
    assert ler_finalizacao(
        {"data": "2026-10-07", "km": "1500", "confirmar": "on"}, manutencao, moto, "cancelada"
    )["status"] == "cancelada"


def test_item_catalogo_converte_zero_em_nulo_e_preserva_ativo():
    assert valores_item_catalogo()["ativo"] is True
    dados = ler_item_catalogo({"nome": " Kit de tração ", "intervalo_km": "5000",
                               "intervalo_minimo_km": "3000", "intervalo_dias": "0", "ativo": "on"})
    assert dados == {"nome": "Kit de tração", "intervalo_km": 5000, "intervalo_minimo_km": 3000,
                     "intervalo_dias": None, "ativo": True}


@pytest.mark.parametrize("valores,campo", [
    ({"nome": "", "intervalo_km": "1000", "intervalo_minimo_km": "0", "intervalo_dias": "0"}, "nome"),
    ({"nome": "X", "intervalo_km": "0", "intervalo_minimo_km": "0", "intervalo_dias": "0"}, "intervalo_km"),
    ({"nome": "X", "intervalo_km": "0", "intervalo_minimo_km": "100", "intervalo_dias": "90"}, "intervalo_minimo_km"),
    ({"nome": "X", "intervalo_km": "5000", "intervalo_minimo_km": "5000", "intervalo_dias": "0"}, "intervalo_minimo_km"),
])
def test_item_catalogo_rejeita_campos_invalidos(valores, campo):
    with pytest.raises(ErroDeCampos) as capturado:
        ler_item_catalogo(valores)
    assert campo in capturado.value.erros
