"""Contrato com mais de uma moto: regra pura e serviço (a moto principal concentra parcela e receita)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.domain.contrato_motos import (
    MAX_MOTOS_POR_CONTRATO,
    contratos_da_moto,
    contratos_por_moto,
    normalizar_motos_vinculadas,
    todas_as_motos,
)
from src.services import contratos

DADOS = {
    "moto_id": "m1",
    "cliente_id": "c",
    "data_inicio": "2026-10-23",
    "periodicidade": "semanal",
    "valor_periodo": "350.00",
    "caucao_valor": "500.00",
    "km_inicial": 100,
}
VISTORIA = {"km": 100}


class TestNormalizar:
    def test_sem_vinculadas_devolve_lista_vazia(self):
        assert normalizar_motos_vinculadas("m1", None) == []
        assert normalizar_motos_vinculadas("m1", []) == []

    def test_ignora_vazios_e_espacos(self):
        assert normalizar_motos_vinculadas("m1", [" m2 ", "", None]) == ["m2"]

    def test_recusa_repeticao(self):
        with pytest.raises(ValueError, match="mais de uma vez"):
            normalizar_motos_vinculadas("m1", ["m2", "m2"])

    def test_recusa_a_principal_na_lista(self):
        with pytest.raises(ValueError, match="principal"):
            normalizar_motos_vinculadas("m1", ["m1"])

    def test_limite_de_motos_conta_a_principal(self):
        ok = [f"v{i}" for i in range(MAX_MOTOS_POR_CONTRATO - 1)]
        assert normalizar_motos_vinculadas("m1", ok) == ok
        with pytest.raises(ValueError, match=str(MAX_MOTOS_POR_CONTRATO)):
            normalizar_motos_vinculadas("m1", ok + ["extra"])

    def test_todas_as_motos_a_principal_vem_primeiro(self):
        assert todas_as_motos("m1", ["m2", "m3"]) == ["m1", "m2", "m3"]


class TestServico:
    def test_criar_contrato_envia_as_vinculadas(self):
        with patch("src.services.contratos.contratos.criar_via_rpc", return_value={}) as rpc:
            contratos.criar_contrato("m1", "c", date(2026, 10, 23), "semanal", Decimal("350.00"), motos_vinculadas=["m2"])
        assert rpc.call_args.args[0]["motos_vinculadas"] == ["m2"]
        assert rpc.call_args.args[0]["moto_id"] == "m1"

    def test_criar_contrato_sem_vinculadas_nao_envia_a_chave(self):
        with patch("src.services.contratos.contratos.criar_via_rpc", return_value={}) as rpc:
            contratos.criar_contrato("m1", "c", date(2026, 10, 23), "semanal", Decimal("350.00"))
        assert "motos_vinculadas" not in rpc.call_args.args[0]

    def test_criar_contrato_recusa_vinculada_igual_a_principal(self):
        with patch("src.services.contratos.contratos.criar_via_rpc") as rpc:
            with pytest.raises(ValueError, match="principal"):
                contratos.criar_contrato("m1", "c", date(2026, 10, 23), "semanal", Decimal("350.00"), motos_vinculadas=["m1"])
        rpc.assert_not_called()

    def test_criar_com_vistoria_valida_e_normaliza_as_vinculadas(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
            contratos.criar_com_vistoria({**DADOS, "motos_vinculadas": [" m2 "]}, VISTORIA)
        assert rpc.call_args.args[0]["motos_vinculadas"] == ["m2"]

    def test_criar_com_vistoria_recusa_repeticao(self):
        with patch("src.services.contratos.contratos.criar_com_vistoria") as rpc:
            with pytest.raises(ValueError, match="mais de uma vez"):
                contratos.criar_com_vistoria({**DADOS, "motos_vinculadas": ["m2", "m2"]}, VISTORIA)
        rpc.assert_not_called()

    def test_motos_do_contrato_le_a_view(self):
        linhas = [{"moto_id": "m1", "principal": True, "placa": "POP9E24"}]
        with patch("src.services.contratos.contratos.listar_motos_do_contrato", return_value=linhas) as leitura:
            assert contratos.motos_do_contrato("ct") == linhas
        leitura.assert_called_once_with("ct")


def test_contar_vinculadas_ordena_pela_chave_composta_porque_contrato_motos_nao_tem_id():
    """Regressão do erro 500 na lista de contratos: `todos()` ordena por `id` por padrão, coluna que a tabela não tem."""
    from src.repositories import contratos as repositorio

    linhas = [{"contrato_id": "c1", "moto_id": "m1"}, {"contrato_id": "c1", "moto_id": "m2"}, {"contrato_id": "c2", "moto_id": "m3"}]
    with patch.object(repositorio, "todos", return_value=linhas) as todos:
        assert repositorio.contar_vinculadas() == {"c1": 2, "c2": 1}
    assert todos.call_args.args == ("contrato_motos",) and "id" not in todos.call_args.kwargs["ordem"]


CONTRATOS = [
    {"id": "c1", "moto_id": "m1", "cliente_id": "yangry", "status": "ativo"},
    {"id": "c2", "moto_id": "m3", "cliente_id": "outro", "status": "ativo"},
    {"id": "c3", "moto_id": "m4", "cliente_id": "antigo", "status": "encerrado"},
]
VINCULOS = [{"contrato_id": "c1", "moto_id": "m2"}, {"contrato_id": "c3", "moto_id": "m5"}]


class TestContratosPorMoto:
    def test_principal_e_vinculada_apontam_para_o_mesmo_contrato(self):
        mapa = contratos_por_moto(CONTRATOS, VINCULOS)
        assert mapa["m1"]["id"] == "c1"
        assert mapa["m2"]["id"] == "c1"

    def test_moto_de_contrato_com_uma_moto_so_continua_funcionando(self):
        assert contratos_por_moto(CONTRATOS, VINCULOS)["m3"]["cliente_id"] == "outro"

    def test_contrato_encerrado_nao_conta_nem_a_principal_nem_a_vinculada(self):
        mapa = contratos_por_moto(CONTRATOS, VINCULOS)
        assert "m4" not in mapa and "m5" not in mapa

    def test_principal_vale_mais_que_vinculada_se_a_moto_aparecer_nos_dois(self):
        vinculos = [{"contrato_id": "c1", "moto_id": "m3"}]
        assert contratos_por_moto(CONTRATOS, vinculos)["m3"]["id"] == "c2"

    def test_sem_vinculos(self):
        assert set(contratos_por_moto(CONTRATOS, [])) == {"m1", "m3"}


class TestContratosDaMoto:
    def test_inclui_como_principal_e_como_vinculada(self):
        assert [c["id"] for c in contratos_da_moto("m1", CONTRATOS, VINCULOS)] == ["c1"]
        assert [c["id"] for c in contratos_da_moto("m2", CONTRATOS, VINCULOS)] == ["c1"]

    def test_inclui_contratos_encerrados(self):
        assert [c["id"] for c in contratos_da_moto("m5", CONTRATOS, VINCULOS)] == ["c3"]

    def test_moto_sem_contrato(self):
        assert contratos_da_moto("m9", CONTRATOS, VINCULOS) == []
