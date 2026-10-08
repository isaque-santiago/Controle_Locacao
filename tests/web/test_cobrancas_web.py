"""Fase 3: lista de Cobranças (abas e paginação) no app FastAPI. Hoje, nos testes, é 07/10/2026."""

from decimal import Decimal

from tests.web.conftest import entrar


def test_abre_em_hoje_com_resumo_de_atraso_e_contagem_nas_abas(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas").text
    assert "R$ 580,00 em atraso · 2 clientes" in html
    for rotulo in ("Hoje · 1", "Atrasadas · 2", "Próximos 7 dias · 2", "Pagas · 2"):
        assert rotulo in html
    assert "Ana &lt;b&gt;Souza&lt;/b&gt;" in html and "BRA-2E19" in html and "07/10/2026" in html and "R$ 204,00" in html
    assert "Bruno Lima" not in html  # só a cobrança de hoje é da Ana


def test_resumo_no_singular_e_sem_atraso(cliente, base_cobrancas):
    entrar(cliente)
    base_cobrancas.cobrancas = [c for c in base_cobrancas.cobrancas if c["id"] != "a2"]
    assert "R$ 280,00 em atraso · 1 cliente" in cliente.get("/cobrancas").text
    base_cobrancas.cobrancas = [c for c in base_cobrancas.cobrancas if c["situacao"] != "atrasada"]
    assert "Nenhuma cobrança em atraso" in cliente.get("/cobrancas").text


def test_atrasadas_mostram_dias_encargos_e_total_do_mais_antigo_ao_mais_novo(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas?aba=atrasadas").text
    assert html.index("20/09/2026") < html.index("01/10/2026")
    # 20/09 -> 17 dias: multa 15 + 7*17 = 134; saldo 300 -> total 434
    assert "17 dia(s)" in html and "R$ 134,00" in html and "R$ 434,00" in html
    # 01/10 -> 6 dias: 15 + 42 = 57; saldo 280 -> total 337
    assert "6 dia(s)" in html and "R$ 57,00" in html and "R$ 337,00" in html


def test_proximos_7_dias_marcam_a_primeira_parcela_e_excluem_hoje_e_o_distante(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas?aba=proximos").text
    assert "10/10/2026" in html and "14/10/2026" in html and "30/10/2026" not in html and "07/10/2026" not in html
    assert html.count("1ª parcela") == 1


def test_pagas_mostram_pagamento_forma_e_o_mais_recente_primeiro(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas?aba=pagas").text
    assert html.index("09/09/2026") < html.index("02/09/2026")
    assert "Dinheiro" in html and "Pix" in html and "R$ 300,00" in html


def test_painel_parcial_traz_as_abas_fora_de_banda_sem_a_pagina(cliente, base_cobrancas):
    entrar(cliente)
    parcial = cliente.get("/cobrancas/abas/atrasadas", headers={"HX-Request": "true"}).text
    assert "<html" not in parcial and 'hx-swap-oob="true"' in parcial and 'id="painel-aba"' in parcial
    assert 'aria-selected="true"' in parcial and "Atrasadas · 2" in parcial
    assert cliente.get("/cobrancas/abas/inexistente").status_code == 404


def test_aba_invalida_cai_em_hoje(cliente, base_cobrancas):
    entrar(cliente)
    assert "Cobranças de hoje" in cliente.get("/cobrancas?aba=xyz").text


def test_aba_vazia_mostra_a_mensagem_da_aba(cliente, base_cobrancas):
    entrar(cliente)
    base_cobrancas.cobrancas = [c for c in base_cobrancas.cobrancas if c["situacao"] != "paga"]
    assert "Nenhuma cobrança paga." in cliente.get("/cobrancas?aba=pagas").text
    base_cobrancas.cobrancas = []
    assert "Nenhuma cobrança vence hoje." in cliente.get("/cobrancas").text


def test_paginacao_de_dez_em_dez_com_url_e_painel_parcial(cliente, base_cobrancas):
    entrar(cliente)
    base_cobrancas.cobrancas = [
        {"id": f"a{i}", "contrato_id": "k1", "cliente_id": "cl1", "moto_id": "m1", "tipo": "locacao",
         "vencimento": f"2026-09-{(i % 27) + 1:02d}", "valor": Decimal("100"), "saldo": Decimal("100"), "situacao": "atrasada"}
        for i in range(23)
    ]
    primeira = cliente.get("/cobrancas?aba=atrasadas").text
    assert "Mostrando 1 a 10 de 23" in primeira and primeira.count("<tr>") == 10 + 1
    assert 'hx-get="/cobrancas/abas/atrasadas?pagina=2"' in primeira and 'hx-push-url="/cobrancas?aba=atrasadas&amp;pagina=2"' in primeira
    ultima = cliente.get("/cobrancas/abas/atrasadas?pagina=99").text
    assert "Mostrando 21 a 23 de 23" in ultima and "pagina=2" in ultima and "pagina=4" not in ultima
    assert "Mostrando 1 a 10 de 23" in cliente.get("/cobrancas?aba=atrasadas&pagina=abc").text
    assert "Mostrando" not in cliente.get("/cobrancas").text  # outras abas curtas não paginam


def test_cobrancas_exigem_dono(cliente, base_cobrancas):
    assert cliente.get("/cobrancas").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/cobrancas").status_code == 403
    assert cliente.get("/cobrancas/abas/hoje").status_code == 403
