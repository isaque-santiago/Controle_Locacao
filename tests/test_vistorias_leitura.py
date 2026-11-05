"""Leitura de vistorias por contrato: o padrão continua sendo a vistoria da moto principal."""

from unittest.mock import MagicMock, patch

from src.repositories import vistorias as repositorio

LINHAS = [
    {"id": "v1", "moto_id": "m1", "tipo": "entrega", "contrato": {"moto_id": "m1"}},
    {"id": "v2", "moto_id": "m2", "tipo": "entrega", "contrato": {"moto_id": "m1"}},
    {"id": "v3", "moto_id": "m1", "tipo": "devolucao", "contrato": {"moto_id": "m1"}},
]


def _cliente(linhas):
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value.eq.return_value
    consulta.order.return_value.execute.return_value.data = linhas
    consulta.eq.return_value.execute.return_value.data = [l for l in linhas if l["tipo"] == "entrega"]
    return cliente


def test_listar_por_contrato_devolve_por_padrao_so_a_moto_principal():
    with patch.object(repositorio, "get_client", return_value=_cliente(LINHAS)):
        assert [v["id"] for v in repositorio.listar_por_contrato("c1")] == ["v1", "v3"]


def test_listar_por_contrato_de_uma_moto():
    with patch.object(repositorio, "get_client", return_value=_cliente(LINHAS)):
        assert [v["id"] for v in repositorio.listar_por_contrato("c1", moto_id="m2")] == ["v2"]


def test_listar_por_contrato_todas():
    with patch.object(repositorio, "get_client", return_value=_cliente(LINHAS)):
        assert len(repositorio.listar_por_contrato("c1", todas=True)) == 3


def test_obter_por_contrato_e_tipo_padrao_e_a_da_principal():
    with patch.object(repositorio, "get_client", return_value=_cliente(LINHAS)):
        assert repositorio.obter_por_contrato_e_tipo("c1", "entrega")["id"] == "v1"
        assert repositorio.obter_por_contrato_e_tipo("c1", "entrega", moto_id="m2")["id"] == "v2"
        assert repositorio.obter_por_contrato_e_tipo("c1", "entrega", moto_id="m9") is None


def test_obter_por_contrato_e_tipo_nao_confunde_a_vinculada_com_a_do_contrato():
    so_vinculada = [LINHAS[1]]
    with patch.object(repositorio, "get_client", return_value=_cliente(so_vinculada)):
        assert repositorio.obter_por_contrato_e_tipo("c1", "entrega") is None
