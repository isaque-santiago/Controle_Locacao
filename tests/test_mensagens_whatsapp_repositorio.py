"""Testes de src/repositories/mensagens_whatsapp.py: as chamadas às RPCs do envio (cliente Supabase falso)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.domain.janela_envio import FUSO
from src.repositories import mensagens_whatsapp as repositorio


def _com_cliente():
    cliente = MagicMock()
    return cliente, patch.object(repositorio, "get_client", return_value=cliente)


def test_registrar_preparo_manda_o_portao_em_iso_e_o_resumo():
    cliente, patcher = _com_cliente()
    with patcher:
        repositorio.registrar_preparo(datetime(2026, 11, 12, 10, 25, tzinfo=FUSO), {"fila": {"enfileiradas": 2}})
    cliente.rpc.assert_called_once_with("rpc_whatsapp_registrar_preparo", {
        "p_liberado_ate": "2026-11-12T10:25:00-03:00", "p_resumo": {"fila": {"enfileiradas": 2}}})
    cliente.rpc.return_value.execute.assert_called_once_with()


def test_registrar_preparo_com_portao_fechado_manda_nulo():
    cliente, patcher = _com_cliente()
    with patcher:
        repositorio.registrar_preparo(None)
    assert cliente.rpc.call_args.args == ("rpc_whatsapp_registrar_preparo", {"p_liberado_ate": None, "p_resumo": None})


def test_reservar_e_registrar_resultado_chamam_as_rpcs_certas():
    cliente, patcher = _com_cliente()
    cliente.rpc.return_value.execute.return_value.data = [{"id": "m1"}]
    with patcher:
        assert repositorio.reservar(5) == [{"id": "m1"}]
        repositorio.registrar_resultado("m1", "enviada", None, "EVO-1")
    assert [c.args for c in cliente.rpc.call_args_list] == [
        ("rpc_whatsapp_reservar", {"p_limite": 5}),
        ("rpc_whatsapp_registrar_resultado", {"p_id": "m1", "p_resultado": "enviada", "p_erro": None, "p_evolution_id": "EVO-1"}),
    ]
