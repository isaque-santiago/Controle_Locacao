"""Fase 3: registrar pagamento de cobrança, em diálogo (HTMX) e em página. Hoje, nos testes, é 07/10/2026."""

from datetime import date
from decimal import Decimal

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _dados(token, **extra):
    return {"csrf_token": token, "data_pagamento": "2026-10-07", "principal": "204,00", "extras": "0,00", "forma": "pix",
            "observacoes": "", "chave_operacao": "chave-1", **extra}


def test_lista_oferece_pagar_so_em_hoje_e_atrasadas(cliente, base_cobrancas):
    entrar(cliente)
    hoje = cliente.get("/cobrancas?aba=hoje").text
    assert 'href="/cobrancas/h1/pagar"' in hoje and 'hx-get="/cobrancas/h1/pagar"' in hoje
    assert 'aria-label="Registrar pagamento de Ana &lt;b&gt;Souza&lt;/b&gt;"' in hoje
    assert 'href="/cobrancas/a1/pagar"' in cliente.get("/cobrancas?aba=atrasadas").text
    for aba in ("proximos", "pagas"):
        assert "/pagar" not in cliente.get(f"/cobrancas?aba={aba}").text


def test_dashboard_leva_ao_pagamento_da_cobranca(cliente, base_cobrancas):
    entrar(cliente)
    assert 'href="/cobrancas/c1/pagar"' in cliente.get("/").text


def test_formulario_em_dialogo_vem_so_com_o_formulario(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/a2/pagar", headers=HX).text
    assert "<html" not in html and 'id="form-dialogo"' in html and "Registrar pagamento" in html
    assert "Bruno Lima" in html and "QRS-4T21" in html and "vencimento <span" in html and "20/09/2026" in html
    # 20/09 -> 17 dias: multa 15 + adicional 119 = 134; total 434
    assert "R$ 15,00" in html and "R$ 119,00" in html and "17 dia(s) de atraso" in html and "R$ 434,00" in html
    assert 'name="principal" type="text" value="300,00"' in html and 'name="extras" type="text" value="134,00"' in html
    assert 'name="chave_operacao" value="' in html and 'hx-post="/cobrancas/a2/pagar/previa"' in html


def test_sem_htmx_o_mesmo_formulario_abre_como_pagina(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/a2/pagar").text
    assert "<html" in html and 'id="form-pagamento"' in html and "Voltar para cobranças" in html
    assert "Confirmar pagamento" in html and 'href="/cobrancas"' in html


def test_chave_de_operacao_muda_a_cada_abertura(cliente, base_cobrancas):
    entrar(cliente)
    abrir = lambda: cliente.get("/cobrancas/h1/pagar", headers=HX).text.split('name="chave_operacao" value="')[1].split('"')[0]
    assert abrir() != abrir()


def test_previa_recalcula_encargos_e_valores_para_a_data(cliente, base_cobrancas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    cabecalhos = {**HX, "X-CSRF-Token": token}
    no_vencimento = cliente.post("/cobrancas/a2/pagar/previa", data={"data_pagamento": "2026-09-20"}, headers=cabecalhos).text
    assert "<html" not in no_vencimento and 'id="bloco-pagamento"' in no_vencimento
    assert "0 dia(s) de atraso" in no_vencimento and 'name="extras" type="text" value="15,00"' in no_vencimento  # só a multa
    mais_tarde = cliente.post("/cobrancas/a2/pagar/previa", data={"data_pagamento": "2026-10-10"}, headers=cabecalhos).text
    assert "20 dia(s) de atraso" in mais_tarde and 'value="155,00"' in mais_tarde and "R$ 455,00" in mais_tarde
    invalida = cliente.post("/cobrancas/a2/pagar/previa", data={"data_pagamento": ""}, headers=cabecalhos)
    assert invalida.status_code == 200 and 'value="0,00"' in invalida.text and "R$ 300,00" in invalida.text


def test_pagamento_total_grava_com_a_chave_e_avisa_que_quitou(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/cobrancas/h1/pagar", data=_dados(token, observacoes=" balcão "), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == "/cobrancas?aba=hoje"
    assert acoes_cobrancas_falsas.pagamentos == [
        ("h1", date(2026, 10, 7), Decimal("204.00"), Decimal("0.00"), "pix", "balcão", "chave-1")
    ]
    assert "Pagamento de R$ 204,00 registrado. Cobrança quitada." in cliente.get("/cobrancas").text


def test_pagamento_parcial_com_encargos_avisa_que_continua_em_aberto(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/cobrancas/a2/pagar", data=_dados(token, principal="100,00", extras="134,00", forma="dinheiro"), headers=HX)
    assert resposta.headers["HX-Redirect"] == "/cobrancas?aba=atrasadas"
    assert acoes_cobrancas_falsas.pagamentos[0][2:5] == (Decimal("100.00"), Decimal("134.00"), "dinheiro")
    aviso = cliente.get("/cobrancas?aba=atrasadas").text
    assert "Multa e adicional de R$ 134,00 incluídos" in aviso and "continua em aberto com o saldo restante" in aviso


def test_sem_htmx_o_pagamento_redireciona_com_303(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    resposta = cliente.post("/cobrancas/h1/pagar", data=_dados(csrf_da_sessao(cliente)))
    assert resposta.status_code == 303 and resposta.headers["location"] == "/cobrancas?aba=hoje"
    assert len(acoes_cobrancas_falsas.pagamentos) == 1


def test_erros_por_campo_mantem_o_dialogo_e_nao_gravam(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    acima = cliente.post("/cobrancas/h1/pagar", data=_dados(token, principal="204,01"), headers=HX)
    assert acima.status_code == 422 and 'id="form-dialogo"' in acima.text
    assert "não pode ser maior que o saldo da cobrança (R$ 204,00)" in acima.text and 'value="204,01"' in acima.text
    varios = cliente.post("/cobrancas/h1/pagar", data=_dados(token, data_pagamento="", principal="0", extras="-1", forma="cheque"), headers=HX)
    assert varios.status_code == 422 and "Data do pagamento:" in varios.text and "Multa e adicional recebidos:" in varios.text
    assert acoes_cobrancas_falsas.pagamentos == []
    assert 'name="chave_operacao" value="chave-1"' in varios.text  # o reenvio corrigido continua idempotente


def test_erro_na_pagina_sem_htmx_devolve_a_pagina_inteira(cliente, base_cobrancas):
    entrar(cliente)
    resposta = cliente.post("/cobrancas/h1/pagar", data=_dados(csrf_da_sessao(cliente), principal="x"))
    assert resposta.status_code == 422 and "<html" in resposta.text and 'id="form-pagamento"' in resposta.text


def test_erro_do_servico_ao_pagar_mostra_a_mensagem(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    acoes_cobrancas_falsas.falhar_com = ValueError("Pagamento maior que o saldo.")
    resposta = cliente.post("/cobrancas/h1/pagar", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 422 and "Pagamento maior que o saldo." in resposta.text


def test_cobranca_paga_ou_inexistente_nao_abre_o_pagamento(cliente, base_cobrancas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    for caminho in ("g1", "naoexiste"):
        assert cliente.get(f"/cobrancas/{caminho}/pagar").status_code == 404
        assert cliente.post(f"/cobrancas/{caminho}/pagar", data=_dados(token), headers=HX).status_code == 404


def test_pagamento_exige_dono_e_csrf(cliente, base_cobrancas):
    assert cliente.get("/cobrancas/h1/pagar").status_code == 303
    entrar(cliente)
    assert cliente.post("/cobrancas/h1/pagar", data=_dados("")).status_code in (400, 403)
    assert cliente.post("/cobrancas/h1/pagar/previa", data={"data_pagamento": "2026-10-07"}).status_code in (400, 403)
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/cobrancas/h1/pagar").status_code == 403


def test_atributos_do_botao_pagar_nao_saem_escapados(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas?aba=atrasadas").text
    assert "&#34;" not in html.split("<main")[1] and 'hx-target="#dlg-form-conteudo"' in html
