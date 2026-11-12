"""Cancelar cobrança (dono), em diálogo (HTMX) e em página. Hoje, nos testes, é 07/10/2026."""

from decimal import Decimal

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _dados(token, **extra):
    return {"csrf_token": token, "motivo": "Lançada por engano", **extra}


def _cobranca(base, id_):
    return next(c for c in base.cobrancas if c["id"] == id_)


def test_lista_oferece_cancelar_em_hoje_atrasadas_e_proximos(cliente, base_cobrancas):
    entrar(cliente)
    hoje = cliente.get("/cobrancas?aba=hoje").text
    assert 'href="/cobrancas/h1/cancelar"' in hoje and 'hx-get="/cobrancas/h1/cancelar"' in hoje
    assert 'aria-label="Cancelar a cobrança de Ana &lt;b&gt;Souza&lt;/b&gt;"' in hoje
    assert 'href="/cobrancas/a1/cancelar"' in cliente.get("/cobrancas?aba=atrasadas").text
    proximos = cliente.get("/cobrancas?aba=proximos").text
    assert 'href="/cobrancas/p1/cancelar"' in proximos and "/pagar" not in proximos
    assert "/cancelar" not in cliente.get("/cobrancas?aba=pagas").text


def test_cobranca_com_pagamento_parcial_nao_ganha_o_botao(cliente, base_cobrancas):
    _cobranca(base_cobrancas, "a1")["valor_pago"] = Decimal("80")
    entrar(cliente)
    atrasadas = cliente.get("/cobrancas?aba=atrasadas").text
    assert 'href="/cobrancas/a1/cancelar"' not in atrasadas and 'href="/cobrancas/a2/cancelar"' in atrasadas
    assert 'href="/cobrancas/a1/pagar"' in atrasadas  # continua podendo receber o restante


def test_formulario_em_dialogo_pede_o_motivo(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/a2/cancelar", headers=HX).text
    assert "<html" not in html and 'id="form-dialogo"' in html and "Cancelar cobrança" in html
    assert "Bruno Lima" in html and "QRS-4T21" in html and "20/09/2026" in html and "R$ 300,00" in html
    assert 'name="motivo"' in html and 'maxlength="200"' in html and 'action="/cobrancas/a2/cancelar"' in html
    assert "btn-perigo" in html


def test_sem_htmx_o_mesmo_formulario_abre_como_pagina(cliente, base_cobrancas):
    entrar(cliente)
    html = cliente.get("/cobrancas/a2/cancelar").text
    assert "<html" in html and 'id="form-cancelar"' in html and "Voltar para cobranças" in html and 'href="/cobrancas"' in html


def test_cancelar_grava_o_motivo_e_volta_para_a_aba_da_cobranca(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    resposta = cliente.post("/cobrancas/a1/cancelar", data=_dados(csrf_da_sessao(cliente), motivo="  Multa indevida  "), headers=HX)
    assert resposta.status_code in (200, 204) and resposta.headers["HX-Redirect"] == "/cobrancas?aba=atrasadas"
    assert acoes_cobrancas_falsas.cancelamentos == [("a1", "Multa indevida")]
    assert "Cobrança de Locação de Ana &lt;b&gt;Souza&lt;/b&gt; (R$ 280,00) cancelada" in cliente.get("/cobrancas?aba=atrasadas").text


def test_sem_htmx_o_cancelamento_redireciona_com_303(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    resposta = cliente.post("/cobrancas/p1/cancelar", data=_dados(csrf_da_sessao(cliente)))
    assert resposta.status_code == 303 and resposta.headers["location"] == "/cobrancas?aba=proximos"
    assert len(acoes_cobrancas_falsas.cancelamentos) == 1


def test_motivo_ausente_ou_curto_mantem_o_dialogo_e_nao_grava(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    for motivo in ("", "  ", "ab"):
        resposta = cliente.post("/cobrancas/h1/cancelar", data=_dados(token, motivo=motivo), headers=HX)
        assert resposta.status_code == 422 and 'id="form-dialogo"' in resposta.text and "mínimo 3 letras" in resposta.text
    longo = cliente.post("/cobrancas/h1/cancelar", data=_dados(token, motivo="x" * 201), headers=HX)
    assert longo.status_code == 422 and "no máximo 200" in longo.text
    assert acoes_cobrancas_falsas.cancelamentos == []


def test_erro_na_pagina_sem_htmx_devolve_a_pagina_inteira_com_o_texto_digitado(cliente, base_cobrancas):
    entrar(cliente)
    resposta = cliente.post("/cobrancas/h1/cancelar", data=_dados(csrf_da_sessao(cliente), motivo="<b"))
    assert resposta.status_code == 422 and "<html" in resposta.text and 'id="form-cancelar"' in resposta.text
    assert "&lt;b</textarea>" in resposta.text


def test_cobranca_com_pagamento_explica_e_nao_chama_o_banco(cliente, base_cobrancas, acoes_cobrancas_falsas):
    _cobranca(base_cobrancas, "a1")["valor_pago"] = Decimal("80")
    entrar(cliente)
    assert "já tem pagamento registrado" in cliente.get("/cobrancas/a1/cancelar", headers=HX).text
    resposta = cliente.post("/cobrancas/a1/cancelar", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 422 and "já tem pagamento registrado e não pode ser cancelada" in resposta.text
    assert acoes_cobrancas_falsas.cancelamentos == []


def test_recusa_do_banco_aparece_no_dialogo(cliente, base_cobrancas, acoes_cobrancas_falsas):
    entrar(cliente)
    acoes_cobrancas_falsas.falhar_com = ValueError("Cobrança paga não pode ser cancelada.")
    resposta = cliente.post("/cobrancas/h1/cancelar", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 422 and "Cobrança paga não pode ser cancelada." in resposta.text


def test_cobranca_paga_cancelada_ou_inexistente_nao_abre(cliente, base_cobrancas):
    _cobranca(base_cobrancas, "f1")["situacao"] = "cancelada"
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    for caminho in ("g1", "f1", "naoexiste"):
        assert cliente.get(f"/cobrancas/{caminho}/cancelar").status_code == 404
        assert cliente.post(f"/cobrancas/{caminho}/cancelar", data=_dados(token), headers=HX).status_code == 404


def test_cancelar_exige_dono_e_csrf(cliente, base_cobrancas, acoes_cobrancas_falsas):
    assert cliente.get("/cobrancas/h1/cancelar").status_code in (303, 401, 403)
    assert cliente.post("/cobrancas/h1/cancelar", data={"motivo": "Lançada por engano"}).status_code in (303, 401, 403)
    entrar(cliente)
    assert cliente.post("/cobrancas/h1/cancelar", data={"motivo": "Lançada por engano"}, headers=HX).status_code == 403
    assert acoes_cobrancas_falsas.cancelamentos == []
