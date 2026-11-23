"""Busca global: rota /busca (fragmento HTMX e página sem JavaScript), acesso e modo de ocultar dados pessoais."""

from types import SimpleNamespace

import pytest

from tests.web.conftest import entrar

HTMX = {"HX-Request": "true", "HX-Target": "busca-resultados"}


@pytest.fixture
def base_busca(monkeypatch):
    from src.web import dados_busca

    motos = [{"id": "00000000-0000-0000-0000-000000000001", "placa": "ABC1D23", "marca": "Honda", "modelo": "CG 160", "tipo": "moto", "status": "alugada"}]
    clientes = [{"id": "c1", "nome": "Joana <b>Prado</b>", "cpf": "123.456.789-09"}]
    contratos = [{"id": "k1", "cliente_id": "c1", "moto_id": motos[0]["id"], "status": "ativo", "data_inicio": "2026-05-10"}]
    monkeypatch.setattr(dados_busca, "motos", SimpleNamespace(listar=lambda: motos))
    monkeypatch.setattr(dados_busca, "clientes", SimpleNamespace(listar=lambda: clientes))
    monkeypatch.setattr(dados_busca, "contratos", SimpleNamespace(listar=lambda: contratos))


def test_exige_login(cliente):
    resposta = cliente.get("/busca?q=abc")
    assert resposta.status_code == 303 and resposta.headers["location"].startswith("/login")


def test_locatario_nao_acessa(cliente):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/busca?q=abc").status_code == 403


def test_fragmento_htmx_traz_grupos_e_links_para_as_fichas(cliente, base_busca):
    entrar(cliente)
    html = cliente.get("/busca?q=joana", headers=HTMX).text
    assert "<html" not in html and 'id="busca-resultados"' in html
    assert 'href="/clientes/c1"' in html and 'href="/contratos/k1"' in html
    assert "Joana &lt;b&gt;Prado&lt;/b&gt;" in html and "<b>Prado</b>" not in html
    assert "CPF ***.456.***-**" in html and "123.456.789-09" not in html


def test_busca_por_placa_leva_a_ficha_do_veiculo(cliente, base_busca):
    entrar(cliente)
    html = cliente.get("/busca?q=abc1d23", headers=HTMX).text
    assert 'href="/motos/00000000-0000-0000-0000-000000000001"' in html and "ABC-1D23" in html


def test_sem_resultado_e_termo_curto(cliente, base_busca):
    entrar(cliente)
    assert "Nada encontrado" in cliente.get("/busca?q=zzzz", headers=HTMX).text
    assert "Digite mais um pouco" in cliente.get("/busca?q=a", headers=HTMX).text
    assert "Digite ao menos" in cliente.get("/busca", headers=HTMX).text


def test_ocultar_dados_pessoais_mascara_nomes_cpf_e_placas(cliente, base_busca):
    entrar(cliente)
    html = cliente.get("/busca?q=joana&ocultar=1", headers=HTMX).text
    assert "Joana" not in html and "Cliente ••••" in html and "CPF ***<" in html.replace("</small>", "<")
    html = cliente.get("/busca?q=abc1d23&ocultar=1", headers=HTMX).text
    assert "ABC-1D23" not in html and "•••-••••" in html


def test_sem_javascript_abre_a_pagina_completa(cliente, base_busca):
    entrar(cliente)
    html = cliente.get("/busca?q=joana").text
    assert "<h1>Buscar</h1>" in html and 'role="search"' in html and 'href="/clientes/c1"' in html


def test_layout_tem_a_paleta_acessivel(cliente, base_busca):
    entrar(cliente)
    html = cliente.get("/motos").text
    assert 'id="dlg-busca"' in html and 'role="combobox"' in html and 'data-abrir="dlg-busca"' in html


def test_layout_tem_a_janela_de_atalhos_com_os_destinos_do_g(cliente, base_busca):
    entrar(cliente)
    html = cliente.get("/motos").text
    assert 'id="dlg-atalhos"' in html and 'data-abrir="dlg-atalhos"' in html
    for letra, caminho in (("v", "/motos"), ("c", "/clientes"), ("o", "/contratos"), ("b", "/cobrancas"), ("i", "/")):
        assert f'href="{caminho}" data-atalho-ir="{letra}"' in html


def test_cada_letra_de_atalho_e_unica_e_leva_a_uma_pagina_do_menu():
    from src.web import navegacao

    letras = [letra for letra, _ in navegacao.ATALHOS_IR]
    assert len(letras) == len(set(letras)) and all(len(l) == 1 and l != "g" for l in letras)
    assert all(item in navegacao.TODOS for _, item in navegacao.ATALHOS_IR)
