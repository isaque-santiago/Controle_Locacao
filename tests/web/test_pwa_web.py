"""App instalável (PWA básico): manifesto, ícones e metadados no <head>, sem service worker."""

import json
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]


def test_manifesto_e_icones_existem_com_os_tamanhos_declarados():
    manifesto = json.loads((RAIZ / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifesto["display"] == "standalone" and manifesto["lang"] == "pt-BR" and manifesto["start_url"] == "/"
    assert {i["purpose"] for i in manifesto["icons"]} == {"any", "maskable"}
    for icone in manifesto["icons"]:
        arquivo = RAIZ / icone["src"].lstrip("/")
        assert Image.open(arquivo).size == tuple(int(n) for n in icone["sizes"].split("x"))
    assert Image.open(RAIZ / "static" / "icones" / "apple-touch-icon.png").size == (180, 180)


def test_manifesto_e_servido_sem_login_com_o_tipo_certo(cliente):
    resposta = cliente.get("/static/manifest.webmanifest")
    assert resposta.status_code == 200 and resposta.headers["content-type"].startswith("application/manifest+json")


def test_pagina_de_login_aponta_para_o_manifesto_e_a_cor_do_tema(cliente):
    html = cliente.get("/login").text
    assert 'rel="manifest" href="/static/manifest.webmanifest' in html
    assert 'rel="apple-touch-icon"' in html and html.count('name="theme-color"') == 2


def test_favicon_ico_nao_da_404(cliente):
    resposta = cliente.get("/favicon.ico")
    assert resposta.status_code == 200 and resposta.headers["content-type"] == "image/png"


def test_paginas_trazem_as_metas_do_iphone_para_a_tela_inicial(cliente):
    html = cliente.get("/login").text
    assert 'name="apple-mobile-web-app-capable" content="yes"' in html
    assert 'name="mobile-web-app-capable" content="yes"' in html
    assert 'name="apple-mobile-web-app-title" content="LA Locadora"' in html
    assert 'name="apple-mobile-web-app-status-bar-style" content="default"' in html


def test_nome_do_app_e_la_locadora_no_manifesto_e_nas_metas(cliente):
    manifesto = json.loads((RAIZ / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifesto["name"] == "LA Locadora" and manifesto["short_name"] == "LA Locadora"
    html = cliente.get("/login").text
    assert 'name="apple-mobile-web-app-title" content="LA Locadora"' in html
    assert "<title>Entrar · LA Locadora</title>" in html or "LA Locadora</title>" in html


def test_marca_das_telas_usa_la_locadora_e_nao_o_nome_antigo(cliente):
    from tests.web.conftest import entrar

    login = cliente.get("/login").text
    assert "LA Locadora" in login and "Controle de Locação" not in login
    entrar(cliente)
    painel = cliente.get("/").text
    assert "LA Locadora" in painel and "Controle de Locação" not in painel and ">CL<" not in painel
