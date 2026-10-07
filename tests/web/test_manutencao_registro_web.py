"""Fase 3: formulário de registro de manutenção."""

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _dados(token, **extra):
    return {"csrf_token": token, "chave_operacao": "chave-1", "moto_id": "m1", "tipo": "preventiva",
            "status": "concluida", "data_entrada": "2026-10-07", "data_saida": "2026-10-07",
            "km": "18420", "oficina": "Central", "descricao": "Revisão", "custo_mao_obra": "30,00",
            "extras_ids": "", **extra}


def test_botao_abre_dialogo_e_sem_htmx_abre_pagina(cliente, base_manutencao):
    entrar(cliente)
    lista = cliente.get("/manutencao").text
    assert 'href="/manutencao/registrar"' in lista and 'hx-get="/manutencao/registrar"' in lista
    dialogo = cliente.get("/manutencao/registrar", headers=HX).text
    assert "<html" not in dialogo and 'id="form-dialogo"' in dialogo and "Salvar manutenção" in dialogo
    pagina = cliente.get("/manutencao/registrar").text
    assert "<html" in pagina and "Voltar para manutenção" in pagina


def test_previa_seleciona_item_adiciona_linha_e_calcula_total(cliente, base_manutencao):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/manutencao/registrar/previa", data=_dados(
        token, item_i1="1", qtd_i1="2", valor_i1="35,00", acao_linha="adicionar"
    ), headers=HX)
    assert resposta.status_code == 200
    html = resposta.text
    assert "Kit de tração" in html and 'name="extra_descricao_0"' in html and "R$ 100,00" in html


def test_trocar_moto_atualiza_o_piso_e_o_km(cliente, base_manutencao):
    entrar(cliente)
    resposta = cliente.post("/manutencao/registrar/previa", data=_dados(
        csrf_da_sessao(cliente), moto_id="m2", km="18420", alteracao="moto"
    ), headers=HX)
    assert 'name="km" type="number" value="9000"' in resposta.text and "9.000 km atuais" in resposta.text


def test_erros_por_campo_preservam_valores_e_nao_gravam(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    resposta = cliente.post("/manutencao/registrar", data=_dados(
        csrf_da_sessao(cliente), data_saida="2026-10-06", km="100", descricao="", custo_mao_obra="x"
    ), headers=HX)
    assert resposta.status_code == 422 and "Corrija os campos destacados" in resposta.text
    for trecho in ("Data de saída", "Quilometragem", "Descrição", "Custo de mão de obra"):
        assert trecho in resposta.text
    assert acoes_manutencao_falsas.registros == []

    moto_invalida = cliente.post("/manutencao/registrar", data=_dados(
        csrf_da_sessao(cliente), moto_id="inexistente"
    ), headers=HX)
    assert moto_invalida.status_code == 422 and "escolha uma das motos disponíveis" in moto_invalida.text


def test_registra_com_itens_chave_e_redireciona_ao_historico(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    resposta = cliente.post("/manutencao/registrar", data=_dados(
        csrf_da_sessao(cliente), item_i1="1", qtd_i1="2", valor_i1="35,00", extras_ids="0",
        extra_descricao_0="Limpeza", extra_qtd_0="1", extra_valor_0="20,00", cobrar_do_cliente="on"
    ), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == "/manutencao?aba=historico"
    dados, chave = acoes_manutencao_falsas.registros[0]
    assert chave == "chave-1" and dados["cobrar_do_cliente"] is True and len(dados["itens"]) == 2
    aviso = cliente.get("/manutencao?aba=historico").text
    assert "Manutenção da moto BRA-2E19 registrada como concluída" in aviso and "R$ 120,00" in aviso


def test_post_sem_htmx_redireciona_e_csrf_e_papel_sao_exigidos(cliente, base_manutencao):
    entrar(cliente)
    resposta = cliente.post("/manutencao/registrar", data=_dados(csrf_da_sessao(cliente)))
    assert resposta.status_code == 303 and resposta.headers["location"] == "/manutencao?aba=historico"
    assert cliente.post("/manutencao/registrar", data=_dados("")).status_code in (400, 403)
    outro = cliente.__class__(cliente.app, follow_redirects=False, raise_server_exceptions=False)
    entrar(outro, identificador="123.456.789-09", senha="senha-locatario")
    assert outro.get("/manutencao/registrar").status_code == 403
