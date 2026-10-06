"""Templates: compatíveis com a CSP (sem script/estilo inline), acessíveis no básico e com macros corretos."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.web.app import criar_app
from tests.web.conftest import entrar

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def catalogo(servico, relogio):
    return TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=True)).get("/componentes").text


def _paginas(cliente, catalogo):
    paginas = {"login": cliente.get("/login").text, "catalogo": catalogo, "erro": cliente.get("/x").text}
    entrar(cliente)
    paginas["inicio"] = cliente.get("/").text
    paginas["migracao"] = cliente.get("/clientes").text
    paginas["motos"] = cliente.get("/motos").text
    cliente.cookies.clear()
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    paginas["portal"] = cliente.get("/portal").text
    return paginas


def test_nenhuma_pagina_usa_estilo_ou_script_inline(cliente, catalogo):
    for nome, html in _paginas(cliente, catalogo).items():
        assert not re.search(r'\sstyle\s*=', html), f"{nome}: atributo style inline"
        assert not re.search(r"<style[\s>]", html), f"{nome}: bloco <style>"
        assert not re.search(r"<script(?![^>]*\ssrc=)", html), f"{nome}: script inline"
        assert not re.search(r'\son[a-z]+\s*=', html), f"{nome}: manipulador de evento inline"


def test_toda_pagina_tem_lang_titulo_h1_e_link_de_pular(cliente, catalogo):
    paginas = _paginas(cliente, catalogo)
    for nome, html in paginas.items():
        assert '<html lang="pt-BR"' in html, nome
        assert re.search(r"<title>[^<]+· Controle de Locação</title>", html), nome
        assert len(re.findall(r"<h1[\s>]", html)) == 1, f"{nome}: precisa de exatamente um h1"
    for nome in ("inicio", "migracao", "motos", "portal", "catalogo"):
        assert 'href="#conteudo"' in paginas[nome], nome


def test_todo_campo_tem_rotulo_associado(cliente, catalogo):
    for nome, html in _paginas(cliente, catalogo).items():
        ids_com_rotulo = set(re.findall(r"<label[^>]*\sfor=\"([^\"]+)\"", html))
        for campo in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
            if 'type="hidden"' in campo:
                continue
            id_ = re.search(r'\sid="([^"]+)"', campo)
            assert id_ and id_.group(1) in ids_com_rotulo, f"{nome}: campo sem rótulo: {campo[:80]}"


def test_botoes_so_com_icone_tem_nome_acessivel(catalogo):
    for botao in re.findall(r'<button class="btn-icone"[^>]*>', catalogo):
        assert "aria-label=" in botao


def test_erro_do_campo_fica_ligado_por_aria(catalogo):
    assert 'aria-invalid="true"' in catalogo
    assert 'aria-describedby="f-placa-erro"' in catalogo
    assert 'id="f-placa-erro"' in catalogo


def test_abas_seguem_o_padrao_aria(catalogo):
    assert 'role="tablist"' in catalogo
    assert catalogo.count('role="tab"') == 2
    assert 'aria-selected="true"' in catalogo and 'tabindex="-1"' in catalogo
    assert 'role="tabpanel"' in catalogo


def test_dialogo_leva_o_token_csrf_e_titulo_associado(catalogo):
    assert 'aria-labelledby="dlg-exemplo-titulo"' in catalogo
    assert 'id="dlg-exemplo-titulo"' in catalogo
    assert 'name="csrf_token"' in catalogo


def test_valores_do_usuario_sao_escapados(cliente):
    pagina = cliente.get("/login")
    resposta = cliente.post(
        "/login",
        data={
            "identificador": '"><script>alert(1)</script>',
            "senha": "x",
            "csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', pagina.text).group(1),
        },
    )
    assert "<script>alert(1)</script>" not in resposta.text
    assert "&lt;script&gt;" in resposta.text


def test_formatos_brasileiros_no_catalogo(catalogo):
    assert "R$ 21.480,00" in catalogo
    assert "R$ 2.310,00" in catalogo


def test_menu_marca_a_pagina_atual_e_a_barra_inferior(cliente):
    entrar(cliente)
    html = cliente.get("/motos").text
    assert re.search(r'<a class="nav-item" href="/motos"[^>]*aria-current="page"', html)
    assert re.search(r'<a href="/motos" aria-current="page">', html)  # barra inferior
    clientes = cliente.get("/clientes").text
    assert re.search(r'<button type="button" data-abrir="dlg-mais" aria-current="page">', clientes)


def test_logout_do_menu_tem_o_token_csrf_da_sessao(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    tokens = set(re.findall(r'name="csrf_token" value="([^"]+)"', html))
    assert len(tokens) == 1 and "" not in tokens
    assert tokens.pop() in html.split("hx-headers=")[1][:80]


def test_css_compilado_existe_e_tem_os_componentes():
    css = (RAIZ / "static" / "css" / "app.css").read_text(encoding="utf-8")
    for classe in (".btn", ".cartao", ".lateral", ".barra-inferior", ".selo", ".aviso"):
        assert classe in css, f"{classe} ausente: rode python scripts/construir_css.py"
    assert "--foco" in css and "prefers-color-scheme:dark" in css.replace(" ", "")
