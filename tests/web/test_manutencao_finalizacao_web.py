"""Fase 3: conclusão e cancelamento de manutenções abertas."""

from datetime import date

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _url(acao):
    return f"/manutencao/h1/{acao}"


def _dados(token, **extra):
    return {"csrf_token": token, "data": "2026-10-07", "km": "18420", **extra}


def test_historico_oferece_acoes_somente_para_aberta(cliente, base_manutencao):
    entrar(cliente)
    html = cliente.get("/manutencao?aba=historico").text
    assert 'hx-get="/manutencao/h1/concluir"' in html and 'hx-get="/manutencao/h1/cancelar"' in html
    assert "/manutencao/h2/concluir" not in html and "/manutencao/h2/cancelar" not in html


def test_dialogos_e_paginas_explicam_impacto(cliente, base_manutencao):
    entrar(cliente)
    concluir = cliente.get(_url("concluir"), headers=HX).text
    assert "<html" not in concluir and "Concluir manutenção" in concluir and "plano dos itens feitos é reiniciado" in concluir
    assert 'value="18420"' in concluir and 'min="18420"' in concluir
    cancelar = cliente.get(_url("cancelar"), headers=HX).text
    assert "Não é possível reabrir" in cancelar and "Entendo que o cancelamento não pode ser desfeito" in cancelar
    assert "btn-perigo" in cancelar and "Manter manutenção" in cancelar
    pagina = cliente.get(_url("concluir")).text
    assert "<html" in pagina and "Voltar para o histórico" in pagina


def test_concluir_grava_e_avisa(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    resposta = cliente.post(_url("concluir"), data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == "/manutencao?aba=historico"
    assert acoes_manutencao_falsas.finalizacoes == [("h1", "concluida", date(2026, 10, 7), 18420)]
    assert "Manutenção da moto BRA-2E19 concluída" in cliente.get("/manutencao?aba=historico").text


def test_cancelar_exige_confirmacao_e_grava_cancelada(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    erro = cliente.post(_url("cancelar"), data=_dados(token), headers=HX)
    assert erro.status_code == 422 and "Marque a confirmação" in erro.text
    assert 'aria-invalid="true"' in erro.text and acoes_manutencao_falsas.finalizacoes == []
    ok = cliente.post(_url("cancelar"), data=_dados(token, confirmar="on"), headers=HX)
    assert ok.headers["HX-Redirect"] == "/manutencao?aba=historico"
    assert acoes_manutencao_falsas.finalizacoes == [("h1", "cancelada", date(2026, 10, 7), 18420)]


def test_data_km_e_erro_do_servico_voltam_ao_formulario(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    invalido = cliente.post(_url("concluir"), data=_dados(token, data="2026-08-31", km="1"), headers=HX)
    assert invalido.status_code == 422 and "posterior à entrada" in invalido.text and "18.420" in invalido.text
    acoes_manutencao_falsas.falhar_com = ValueError("A manutenção já foi finalizada.")
    falha = cliente.post(_url("concluir"), data=_dados(token), headers=HX)
    assert falha.status_code == 422 and "já foi finalizada" in falha.text


def test_finalizada_inexistente_acao_invalida_papel_e_csrf_sao_recusados(cliente, base_manutencao):
    assert cliente.get(_url("concluir")).status_code == 303
    entrar(cliente)
    assert cliente.get("/manutencao/h2/concluir").status_code == 404
    assert cliente.get("/manutencao/naoexiste/concluir").status_code == 404
    assert cliente.get("/manutencao/h1/reabrir").status_code == 404
    assert cliente.post(_url("concluir"), data=_dados("")).status_code in (400, 403)
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(_url("concluir")).status_code == 403
