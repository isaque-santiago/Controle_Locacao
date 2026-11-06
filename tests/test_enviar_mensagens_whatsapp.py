"""Testes de src/enviar_mensagens_whatsapp.py: códigos de saída da rodada agendada."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from src import enviar_mensagens_whatsapp as script
from src.services.autenticacao import CredenciaisInvalidas
from src.services.evolution import EvolutionConfiguracaoInvalida


@pytest.fixture
def ambiente(monkeypatch):
    chamadas = SimpleNamespace(executou=0, evolution=None)

    monkeypatch.setattr(script, "get_servico_mensagens", lambda: ("robo@exemplo.com", "s"))
    monkeypatch.setattr(script, "get_textos_whatsapp", lambda: {"empresa": "LA Motos", "contato": None, "pix": None, "link_portal": None})
    monkeypatch.setattr(script, "ServicoAutenticacao", lambda: SimpleNamespace(entrar=lambda e, s: SimpleNamespace(access_token="tok")))
    monkeypatch.setattr(script.db, "criar_cliente_autenticado", lambda token: object())

    @contextmanager
    def usar_cliente(cliente):
        yield cliente

    monkeypatch.setattr(script.db, "usar_cliente", usar_cliente)

    def executar(evolution, opcoes):
        chamadas.executou += 1
        chamadas.evolution = evolution
        return {"ativo": False}

    monkeypatch.setattr(script.whatsapp, "executar", executar)
    return chamadas


def test_rodada_ok_imprime_o_resumo(ambiente, capsys):
    assert script.principal() == 0
    assert json.loads(capsys.readouterr().out) == {"ativo": False}
    assert ambiente.executou == 1


def test_envio_desligado_nao_exige_a_evolution_configurada(ambiente, monkeypatch):
    monkeypatch.setattr(script, "get_evolution", lambda: (_ for _ in ()).throw(RuntimeError("não deveria ser lida")))
    assert script.principal() == 0  # a Evolution só é criada quando há o que enviar


def test_usuario_de_servico_sem_configuracao(ambiente, monkeypatch):
    def falta():
        raise RuntimeError("faltam SERVICO_MENSAGENS_EMAIL")
    monkeypatch.setattr(script, "get_servico_mensagens", falta)
    assert script.principal() == 2 and ambiente.executou == 0


def test_login_recusado(ambiente, monkeypatch):
    def recusa(e, s):
        raise CredenciaisInvalidas()
    monkeypatch.setattr(script, "ServicoAutenticacao", lambda: SimpleNamespace(entrar=recusa))
    assert script.principal() == 2 and ambiente.executou == 0


def test_chave_da_evolution_recusada(ambiente, monkeypatch):
    def executar(evolution, opcoes):
        raise EvolutionConfiguracaoInvalida("A Evolution recusou a chave (EVOLUTION_APIKEY).")
    monkeypatch.setattr(script.whatsapp, "executar", executar)
    assert script.principal() == 2


def test_erro_inesperado_sai_com_1(ambiente, monkeypatch):
    def executar(evolution, opcoes):
        raise ValueError("boom")
    monkeypatch.setattr(script.whatsapp, "executar", executar)
    assert script.principal() == 1


def test_evolution_criada_sob_demanda_e_fechada(ambiente, monkeypatch):
    fechou = []
    cliente = SimpleNamespace(fechar=lambda: fechou.append(True))
    monkeypatch.setattr(script, "_cliente_evolution", lambda: cliente)

    def executar(evolution, opcoes):
        assert evolution() is cliente
        return {"ativo": True}

    monkeypatch.setattr(script.whatsapp, "executar", executar)
    assert script.principal() == 0 and fechou == [True]
