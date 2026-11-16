"""Configurações: padronizar os acessos de todos os locatários (botão com confirmação; só o dono)."""

from types import SimpleNamespace

from src.web import acoes_configuracoes
from tests.web.conftest import csrf_da_sessao, entrar


def _base(monkeypatch, resposta=None, erro=None):
    chamadas = []

    def padronizar():
        chamadas.append(1)
        if erro:
            raise erro
        return resposta

    monkeypatch.setattr(acoes_configuracoes, "portal_locatario", SimpleNamespace(padronizar_todos_acessos=padronizar))
    return chamadas


def test_pagina_oferece_o_botao_com_confirmacao(cliente):
    entrar(cliente)
    html = cliente.get("/configuracoes").text
    assert "Acessos dos locatários" in html and 'action="/configuracoes/acessos-locatarios/padronizar"' in html
    assert "nome.sobrenome@locadora.com" in html and "data-confirmar=" in html


def test_padronizar_avisa_quantos_e_volta_para_o_cartao(cliente, monkeypatch):
    chamadas = _base(monkeypatch, {"total": 3, "itens": [], "falhas": []})
    entrar(cliente)
    resposta = cliente.post("/configuracoes/acessos-locatarios/padronizar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 303 and resposta.headers["location"] == "/configuracoes#cfg-acessos"
    assert chamadas == [1]
    assert "3 acesso(s) de locatário padronizado(s)." in cliente.get("/configuracoes").text


def test_falha_parcial_vira_alerta(cliente, monkeypatch):
    _base(monkeypatch, {"total": 2, "itens": [], "falhas": [{"cliente_id": "c", "nome": "X", "motivo": "cliente sem nome"}]})
    entrar(cliente)
    cliente.post("/configuracoes/acessos-locatarios/padronizar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert "1 não puderam ser padronizados" in cliente.get("/configuracoes").text


def test_erro_mostra_a_mensagem(cliente, monkeypatch):
    _base(monkeypatch, erro=ValueError("Somente o proprietário pode gerenciar acessos."))
    entrar(cliente)
    resposta = cliente.post("/configuracoes/acessos-locatarios/padronizar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 303
    assert "Somente o proprietário" in cliente.get("/configuracoes").text


def test_sem_csrf_e_recusado(cliente, monkeypatch):
    chamadas = _base(monkeypatch, {"total": 1, "itens": [], "falhas": []})
    entrar(cliente)
    assert cliente.post("/configuracoes/acessos-locatarios/padronizar", data={}).status_code in (400, 403)
    assert chamadas == []
