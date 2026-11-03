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
