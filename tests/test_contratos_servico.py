"""Serviço de contratos: prazo indeterminado e danos descontados da caução (seções 14.3 e 14.4)."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from src.services import contratos

DADOS = {
    "moto_id": "m",
    "cliente_id": "c",
    "data_inicio": "2026-10-05",
    "periodicidade": "semanal",
    "valor_periodo": "350.00",
    "caucao_valor": "1000.00",
    "km_inicial": 100,
}
VISTORIA = {"km": 100}


def test_cria_contrato_por_prazo_indeterminado_sem_data_final():
    with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
        contratos.criar_com_vistoria({**DADOS, "data_fim_prevista": None}, VISTORIA)
    assert rpc.call_args.args[0]["data_fim_prevista"] is None


def test_cria_contrato_sem_a_chave_de_data_final_tambem_e_indeterminado():
    with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
        contratos.criar_com_vistoria(dict(DADOS), VISTORIA)
    assert rpc.call_args.args[0]["data_fim_prevista"] is None


def test_cria_contrato_com_prazo_definido_mantem_a_data():
    with patch("src.services.contratos.contratos.criar_com_vistoria", return_value={}) as rpc:
        contratos.criar_com_vistoria({**DADOS, "data_fim_prevista": "2026-12-28"}, VISTORIA)
    assert rpc.call_args.args[0]["data_fim_prevista"] == "2026-12-28"


def test_recusa_data_final_anterior_ao_inicio():
    with patch("src.services.contratos.contratos.criar_com_vistoria") as rpc:
        with pytest.raises(ValueError, match="fim do contrato"):
            contratos.criar_com_vistoria({**DADOS, "data_fim_prevista": "2026-10-01"}, VISTORIA)
    rpc.assert_not_called()


def test_previa_indeterminada_mostra_so_a_janela_inicial():
    from datetime import date

    agenda = contratos.previa_agenda(date(2026, 10, 5), "semanal", Decimal("350.00"))
    assert [p["numero"] for p in agenda] == [1, 2, 3, 4, 5]


def test_encerra_enviando_os_danos_e_a_descricao():
    from datetime import date

    with patch("src.services.contratos.contratos.encerrar_com_vistoria", return_value={}) as rpc:
        contratos.encerrar_com_vistoria("ct", date(2026, 10, 5), VISTORIA, Decimal("300.00"), "  Retrovisor  ")
    assert rpc.call_args.args == ("ct", date(2026, 10, 5), VISTORIA, Decimal("300.00"), "Retrovisor")


def test_encerra_sem_danos_por_padrao():
    from datetime import date

    with patch("src.services.contratos.contratos.encerrar_com_vistoria", return_value={}) as rpc:
        contratos.encerrar_com_vistoria("ct", date(2026, 10, 5), VISTORIA)
    assert rpc.call_args.args[3:] == (Decimal("0"), None)


@pytest.mark.parametrize("danos,descricao", [(Decimal("50"), None), (Decimal("50"), "   ")])
def test_encerrar_com_danos_exige_descricao(danos, descricao):
    from datetime import date

    with patch("src.services.contratos.contratos.encerrar_com_vistoria") as rpc:
        with pytest.raises(ValueError, match="Descreva os danos"):
            contratos.encerrar_com_vistoria("ct", date(2026, 10, 5), VISTORIA, danos, descricao)
    rpc.assert_not_called()


def test_encerrar_recusa_danos_negativos():
    from datetime import date

    with patch("src.services.contratos.contratos.encerrar_com_vistoria") as rpc:
        with pytest.raises(ValueError, match="negativo"):
            contratos.encerrar_com_vistoria("ct", date(2026, 10, 5), VISTORIA, Decimal("-1"), "x")
    rpc.assert_not_called()


def test_encerrar_contrato_direto_valida_e_repassa_os_danos():
    from datetime import date

    with patch("src.services.contratos.contratos.encerrar_via_rpc", return_value={}) as rpc:
        contratos.encerrar_contrato("ct", date(2026, 10, 5), 150, Decimal("10.00"), "Arranhão")
    assert rpc.call_args.args == ("ct", date(2026, 10, 5), 150, Decimal("10.00"), "Arranhão")
