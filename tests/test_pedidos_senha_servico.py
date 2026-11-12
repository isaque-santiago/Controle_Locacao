"""Testes do serviço e do repositório dos pedidos de senha nova do portal (lado do dono), com o Supabase falso."""

from unittest.mock import MagicMock, patch

import pytest

from src.domain.painel import TOM_ATENCAO, ItemAlerta
from src.repositories import pedidos_senha as repositorio
from src.services import pedidos_senha as servico
from src.web import acoes_clientes

REPO = "src.services.pedidos_senha.pedidos_senha"


# ------------------------------------------------------------------ serviço --


def test_alerta_do_dashboard_cita_os_clientes_com_pedido_aberto():
    abertos = [{"clientes": {"nome": "Maria Souza"}}, {"clientes": {"nome": "João"}}]
    with patch(f"{REPO}.listar_abertos", return_value=abertos):
        assert servico.alertas() == [ItemAlerta(2, "Nova senha do portal pedida", "Maria Souza e mais 1", TOM_ATENCAO, "clientes")]


def test_sem_pedidos_nao_ha_alerta():
    with patch(f"{REPO}.listar_abertos", return_value=[]):
        assert servico.alertas() == []


def test_falha_ao_ler_nao_derruba_o_dashboard():
    with patch(f"{REPO}.listar_abertos", side_effect=RuntimeError("tabela inexistente")):
        assert servico.alertas() == []


def test_falha_ao_ler_o_pedido_da_ficha_vira_sem_pedido():
    with patch(f"{REPO}.aberto_do_cliente", side_effect=RuntimeError("tabela inexistente")):
        assert servico.aberto_do_cliente("c1") is None
    with patch(f"{REPO}.aberto_do_cliente", return_value={"id": "p1"}):
        assert servico.aberto_do_cliente("c1") == {"id": "p1"}


def test_dispensar_fecha_como_dispensado_e_a_falha_sobe_para_a_tela():
    with patch(f"{REPO}.fechar") as fechar:
        servico.dispensar("c1")
    fechar.assert_called_once_with("c1", "dispensado")
    with patch(f"{REPO}.fechar", side_effect=RuntimeError("fora do ar")):
        with pytest.raises(RuntimeError):
            servico.dispensar("c1")


def test_atender_fecha_como_atendido_e_a_falha_nao_sobe():
    with patch(f"{REPO}.fechar") as fechar:
        servico.atender("c1")
    fechar.assert_called_once_with("c1", "atendido")
    with patch(f"{REPO}.fechar", side_effect=RuntimeError("fora do ar")):
        servico.atender("c1")  # a senha já foi trocada: não pode esconder isso do dono


# --------------------------------------------------- ações da tela de Clientes --


def test_gerar_senha_nova_fecha_o_pedido_so_depois_de_dar_certo():
    with patch("src.web.acoes_clientes.portal_locatario.redefinir_senha", return_value={"email": "e", "senha": "s"}) as redefinir, \
         patch("src.web.acoes_clientes.pedidos_senha.atender") as atender:
        assert acoes_clientes.redefinir_senha_portal("c1") == {"email": "e", "senha": "s"}
    redefinir.assert_called_once_with("c1")
    atender.assert_called_once_with("c1")


def test_senha_que_nao_foi_gerada_deixa_o_pedido_aberto():
    with patch("src.web.acoes_clientes.portal_locatario.redefinir_senha", side_effect=ValueError("Falhou")), \
         patch("src.web.acoes_clientes.pedidos_senha.atender") as atender:
        with pytest.raises(ValueError):
            acoes_clientes.redefinir_senha_portal("c1")
    atender.assert_not_called()


def test_remover_o_acesso_fecha_o_pedido():
    with patch("src.web.acoes_clientes.portal_locatario.remover_acesso") as remover, \
         patch("src.web.acoes_clientes.pedidos_senha.atender") as atender:
        acoes_clientes.remover_acesso_portal("c1")
    remover.assert_called_once_with("c1")
    atender.assert_called_once_with("c1")


def test_dispensar_pedido_chama_o_servico():
    with patch("src.web.acoes_clientes.pedidos_senha.dispensar") as dispensar:
        acoes_clientes.dispensar_pedido_senha("c1")
    dispensar.assert_called_once_with("c1")


# -------------------------------------------------------------- repositório --


def _cliente_com(dados):
    cliente = MagicMock()
    consulta = cliente.table.return_value
    for metodo in ("select", "eq", "order", "limit", "update"):
        getattr(consulta, metodo).return_value = consulta
    consulta.execute.return_value.data = dados
    return cliente, consulta


def test_repositorio_lista_so_os_abertos_do_mais_antigo_ao_mais_novo():
    cliente, consulta = _cliente_com([{"id": "p1"}])
    with patch("src.repositories.pedidos_senha.get_client", return_value=cliente):
        assert repositorio.listar_abertos() == [{"id": "p1"}]
    cliente.table.assert_called_once_with("pedidos_senha_portal")
    consulta.eq.assert_called_once_with("status", "aberto")
    consulta.order.assert_called_once_with("pedido_em")


def test_repositorio_aberto_do_cliente_devolve_um_ou_nenhum():
    cliente, consulta = _cliente_com([{"id": "p1"}])
    with patch("src.repositories.pedidos_senha.get_client", return_value=cliente):
        assert repositorio.aberto_do_cliente("c1") == {"id": "p1"}
    assert [c.args for c in consulta.eq.call_args_list] == [("cliente_id", "c1"), ("status", "aberto")]
    cliente, _ = _cliente_com([])
    with patch("src.repositories.pedidos_senha.get_client", return_value=cliente):
        assert repositorio.aberto_do_cliente("c1") is None


def test_repositorio_fecha_so_o_pedido_aberto_com_a_data_de_agora():
    cliente, consulta = _cliente_com([{"id": "p1"}])
    with patch("src.repositories.pedidos_senha.get_client", return_value=cliente):
        assert repositorio.fechar("c1", "atendido") == [{"id": "p1"}]
    dados = consulta.update.call_args.args[0]
    assert dados["status"] == "atendido" and dados["fechado_em"]
    assert [c.args for c in consulta.eq.call_args_list] == [("cliente_id", "c1"), ("status", "aberto")]
