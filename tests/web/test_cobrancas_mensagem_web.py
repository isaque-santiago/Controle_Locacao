"""Fase 3: mensagem de cobrança (diálogo e página) e botão de copiar. Hoje, nos testes, é 07/10/2026."""

from pathlib import Path

from tests.web.conftest import entrar

HX = {"HX-Request": "true"}


def test_lista_oferece_mensagem_ao_lado_do_pagar(cliente, base_cobrancas):
    entrar(cliente)
    for aba, id_ in (("hoje", "h1"), ("atrasadas", "a1")):
        html = cliente.get(f"/cobrancas?aba={aba}").text
        assert f'href="/cobrancas/{id_}/mensagem"' in html and f'hx-get="/cobrancas/{id_}/mensagem"' in html
        assert 'aria-label="Mensagem de cobrança para Ana &lt;b&gt;Souza&lt;/b&gt;"' in html
    assert "/mensagem" not in cliente.get("/cobrancas?aba=proximos").text


def test_dialogo_traz_o_texto_de_atraso_escapado_e_o_botao_de_copiar(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/a2/mensagem", headers=HX).text
    assert "<html" not in html and 'id="dlg-form-titulo"' in html and "data-fechar" in html
    assert "Olá, Bruno Lima. A cobrança de 20/09/2026, referente à moto QRS-4T21, está em atraso há 17 dia(s)" in html
    assert "saldo de R$ 300,00 antes dos encargos" in html
    assert 'data-copiar="texto-mensagem"' in html and 'data-copiar-aviso="aviso-copia"' in html
    assert 'id="texto-mensagem"' in html and "readonly" in html and 'role="status"' in html


def test_mensagem_de_cobranca_que_vence_hoje_nao_fala_em_atraso(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/h1/mensagem", headers=HX).text
    assert "vence na data indicada" in html and "em atraso há" not in html
    assert "Ana &lt;b&gt;Souza&lt;/b&gt;" in html  # nome do cliente escapado no texto e no cabeçalho


def test_sem_htmx_a_mensagem_abre_como_pagina(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/a2/mensagem").text
    assert "<html" in html and "Voltar para cobranças" in html and 'data-copiar="texto-mensagem"' in html


def test_cobranca_paga_ou_inexistente_nao_tem_mensagem(cliente, base_cobrancas):
    entrar(cliente)
    assert cliente.get("/cobrancas/g1/mensagem").status_code == 404
    assert cliente.get("/cobrancas/naoexiste/mensagem").status_code == 404


def test_mensagem_exige_dono(cliente, base_cobrancas):
    assert cliente.get("/cobrancas/a2/mensagem").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/cobrancas/a2/mensagem").status_code == 403


def test_js_tem_o_tratador_de_copiar_sem_script_inline():
    js = (Path(__file__).resolve().parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "[data-copiar]" in js and "navigator.clipboard.writeText" in js
