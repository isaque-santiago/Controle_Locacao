"""Páginas de Dívidas: acesso e conteúdo."""

from tests.web.conftest import entrar


def test_lista_exige_login(cliente):
    resposta = cliente.get("/dividas")
    assert resposta.status_code == 303 and resposta.headers["location"].startswith("/login")


def test_lista_mostra_totais_em_reais_e_cada_divida(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "<h1>Dívidas</h1>" in html and "2 dívidas em aberto" in html
    assert "R$ 10.600,00" in html and "R$ 7.600,00" in html and "Parcelas atrasadas" in html
    assert "10/10/2026" in html and "Nilson" in html
    assert "R$ 14.000,00" in html and "R$ 11.000,00" in html and "R$ 3.000,00" in html
    assert 'href="/dividas/d2"' in html and "OID-7656" in html


def test_lista_mostra_situacoes_e_saldo_confirmado(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "Parcela atrasada (2)" in html and "Quitada" in html and "Em aberto" in html
    assert "confirmado" in html and "Moto fiado" in html and "Empréstimo" in html


def test_nomes_do_banco_sao_escapados_na_lista(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "Celta <b>Zero</b>" not in html and "Celta &lt;b&gt;Zero&lt;/b&gt;" in html


def test_lista_vazia_mostra_estado_vazio(cliente, base_dividas):
    base_dividas.linhas = []
    base_dividas.totais = {"total_em_aberto": 0, "moto_fiado": 0, "dividas_em_aberto": 0, "parcelas_atrasadas": 0,
                           "proximo_vencimento": None, "proximo_credor": None}
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "Nenhuma dívida cadastrada" in html and "0 dívidas em aberto" in html


def test_menu_tem_dividas_e_marca_a_pagina_atual(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert 'href="/dividas"' in html and 'aria-current="page"' in html
