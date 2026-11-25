"""Configurações: planilha de conferência do histórico dos chats (só o dono; com CSRF; sem cache)."""

from starlette.testclient import TestClient

from tests.web.conftest import CPF_LOCATARIO, csrf_da_sessao, entrar, extrair_csrf

URL = "/configuracoes/historico-chats/planilha"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_pagina_explica_e_oferece_o_botao(cliente, base_configuracoes):
    entrar(cliente)
    html = cliente.get("/configuracoes").text
    assert "Histórico dos chats" in html and f'action="{URL}"' in html and "Baixar a conferência (xlsx)" in html and "Decisão" in html


def test_baixa_o_xlsx_sem_cache(cliente, base_configuracoes, monkeypatch):
    from src.web import dados_configuracoes

    monkeypatch.setattr(dados_configuracoes.historico_chat, "planilha_de_conferencia", lambda: b"PK\x03\x04planilha")
    entrar(cliente)
    r = cliente.post(URL, data={"csrf_token": csrf_da_sessao(cliente)})
    assert r.status_code == 200 and r.headers["content-type"] == XLSX and r.content == b"PK\x03\x04planilha"
    assert r.headers["content-disposition"].startswith('attachment; filename="historico-chats-') and r.headers["content-disposition"].endswith('.xlsx"')
    assert r.headers["cache-control"] == "no-store"


def test_exige_csrf_e_dono(cliente, base_configuracoes, monkeypatch):
    from src.web import dados_configuracoes

    chamadas = []
    monkeypatch.setattr(dados_configuracoes.historico_chat, "planilha_de_conferencia", lambda: chamadas.append(1) or b"x")
    assert cliente.post(URL, data={"csrf_token": "x"}).status_code in (303, 401, 403)  # sem login
    entrar(cliente)
    assert cliente.post(URL, data={"csrf_token": "errado"}).status_code == 403
    assert chamadas == []
    locatario = TestClient(cliente.app, follow_redirects=False, raise_server_exceptions=False)  # outro navegador, no mesmo app
    entrar(locatario, identificador=CPF_LOCATARIO, senha="senha-locatario")
    assert locatario.post(URL, data={"csrf_token": extrair_csrf(locatario.get("/portal").text)}).status_code == 403 and chamadas == []
