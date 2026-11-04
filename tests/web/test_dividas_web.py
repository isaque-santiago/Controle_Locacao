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


def test_ficha_mostra_resumo_parcelas_e_pagamentos(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert "Compra parcelada" in html and "OID-7656" in html and "entrada de R$ 5.000,00" in html
    assert "R$ 14.000,00" in html and "R$ 11.000,00" in html and "R$ 3.000,00" in html and "9 x R$ 1.000,00" in html
    assert "vence todo dia 28" in html and "28/11/2026" in html
    assert "Atrasada · 34 d" in html and "A vencer" in html and "Paga" in html
    assert "estimada" in html and "Entrada da compra" in html and "01/05/2026" in html


def test_ficha_so_oferece_pagar_nas_parcelas_em_aberto(cliente):
    from tests.web.conftest import DIVIDA_ID, PARCELA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert f'href="/dividas/parcelas/{PARCELA_ID}/pagar"' in html and 'href="/dividas/parcelas/v9/pagar"' in html
    assert 'href="/dividas/parcelas/v7/pagar"' not in html


def test_ficha_escapa_textos_do_banco(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert "Celta <b>Zero</b>" not in html and "Celta &lt;b&gt;Zero&lt;/b&gt;" in html
    assert "<i>de boca</i>" not in html and "&lt;i&gt;de boca&lt;/i&gt;" in html


def test_ficha_inexistente_ou_com_id_invalido_e_404(cliente):
    entrar(cliente)
    assert cliente.get("/dividas/00000000-0000-0000-0000-0000000000ff").status_code == 404
    assert cliente.get("/dividas/isso-nao-e-um-uuid").status_code == 404


def test_ficha_exige_login(cliente):
    from tests.web.conftest import DIVIDA_ID

    assert cliente.get(f"/dividas/{DIVIDA_ID}").status_code == 303


def test_ficha_com_diferenca_de_saldo_confirmado_avisa(cliente, base_dividas):
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_ID

    f = base_dividas.fichas[DIVIDA_ID]
    f["diferenca"] = Decimal("-1350.00")
    f["saldo_confirmado"] = Decimal("3425.00")
    f["divida"]["confirmado_em"] = "2026-10-16"
    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert "difere do calculado" in html and "confirmado por você em 16/10/2026" in html
