"""Testes de src/services/whatsapp_painel.py com repositórios falsos."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.services import whatsapp_painel as servico

AGORA = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)


def _instalar(monkeypatch, **repos):
    for nome, objeto in repos.items():
        monkeypatch.setattr(servico, nome, objeto)


def test_listar_achata_cliente_e_assuntos(monkeypatch):
    bruto = [{"id": "m1", "status": "enviada", "clientes": {"nome": "Maria"}, "mensagens_whatsapp_itens": [{"tipo": "atraso"}]}]
    _instalar(monkeypatch, repo=SimpleNamespace(listar_recentes=lambda limite, **kw: bruto))
    assert servico.listar_recentes() == [{"id": "m1", "status": "enviada", "cliente": "Maria", "tipos": ["atraso"]}]


def test_listar_do_cliente_filtra_pelo_cliente(monkeypatch):
    pedidos = []
    _instalar(monkeypatch, repo=SimpleNamespace(listar_recentes=lambda limite, **kw: pedidos.append((limite, kw)) or []))
    servico.listar_do_cliente("c1", 10)
    assert pedidos == [(10, {"cliente_id": "c1"})]


def test_cancelar_e_reenviar_avisam_quando_a_mensagem_mudou(monkeypatch):
    _instalar(monkeypatch, repo=SimpleNamespace(cancelar=lambda i: [], reenviar=lambda i: []))
    for acao in (servico.cancelar, servico.reenviar):
        with pytest.raises(ValueError, match="mudou de situação"):
            acao("m1")
    _instalar(monkeypatch, repo=SimpleNamespace(cancelar=lambda i: [{"id": i}], reenviar=lambda i: [{"id": i}]))
    servico.cancelar("m1")
    servico.reenviar("m1")


def test_bloquear_grava_motivo_e_data_e_desbloquear_limpa(monkeypatch):
    gravados = []
    _instalar(monkeypatch, repo_clientes=SimpleNamespace(atualizar=lambda i, d: gravados.append((i, d)) or d))
    servico.bloquear("c1", "Pediu ao dono")
    servico.desbloquear("c1")
    bloqueio, desbloqueio = gravados[0][1], gravados[1][1]
    assert bloqueio["nao_enviar_whatsapp"] is True and bloqueio["motivo_bloqueio_whatsapp"] == "Pediu ao dono"
    assert datetime.fromisoformat(bloqueio["bloqueio_whatsapp_em"]).tzinfo is not None
    assert desbloqueio == {"nao_enviar_whatsapp": False, "motivo_bloqueio_whatsapp": None, "bloqueio_whatsapp_em": None}


def test_controles_so_aceitam_os_campos_do_whatsapp(monkeypatch):
    gravados = []
    _instalar(monkeypatch, repo_configuracoes=SimpleNamespace(atualizar=lambda d: gravados.append(d) or d))
    servico.atualizar_controles({"whatsapp_ativo": True, "whatsapp_modo_teste": True, "whatsapp_numero_teste": None, "whatsapp_max_repeticoes": 10})
    assert len(gravados) == 1
    with pytest.raises(ValueError, match="multa_atraso_valor"):
        servico.atualizar_controles({"multa_atraso_valor": "0"})
    assert len(gravados) == 1


def test_alertas_sem_o_envio_ligado_nao_consultam_o_banco(monkeypatch):
    def nao_deve_ler(*a, **k):
        raise AssertionError("não deveria ler")
    _instalar(monkeypatch, repo=SimpleNamespace(listar_recentes=nao_deve_ler))
    assert servico.alertas({"whatsapp_ativo": False}, AGORA) == []


def test_alertas_sobrevivem_a_banco_sem_as_tabelas(monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("relation does not exist")
    _instalar(monkeypatch, repo=SimpleNamespace(listar_recentes=quebra))
    assert servico.alertas({"whatsapp_ativo": True}, AGORA) == []


def test_alertas_usam_as_mensagens_dos_ultimos_7_dias(monkeypatch):
    pedidos = []
    _instalar(monkeypatch, repo=SimpleNamespace(listar_recentes=lambda limite, **kw: pedidos.append(kw) or []))
    config = {"whatsapp_ativo": True, "whatsapp_modo_teste": True, "whatsapp_ultimo_estado": "open",
              "whatsapp_ultima_rodada_em": AGORA.isoformat()}
    itens = servico.alertas(config, AGORA)
    assert [i.titulo for i in itens] == ["WhatsApp em modo teste"]
    assert pedidos[0]["desde"] == datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc)
