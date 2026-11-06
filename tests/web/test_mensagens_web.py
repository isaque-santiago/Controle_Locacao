"""Página Mensagens: lista de WhatsApp com filtro, cancelar e reenviar (só o dono)."""

from tests.web.conftest import MENSAGEM_ENVIADA, MENSAGEM_FALHOU, MENSAGEM_PENDENTE, csrf_da_sessao, entrar


def test_mostra_primeiro_o_que_tem_problema(cliente, base_whatsapp):
    entrar(cliente)
    html = cliente.get("/mensagens").text
    assert "Mensagens" in html and "WhatsApp enviado aos locatários" in html
    assert "Com problema <b>1</b>" in html and "Aguardando <b>1</b>" in html and "Enviadas <b>1</b>" in html and "Todas <b>3</b>" in html
    assert "A Evolution recusou o pedido (400)." in html and "3 tentativa(s)" in html
    assert "Maria Souza" in html and "(11) 98888-7777" in html and "Pagamento em atraso" in html
    assert "Olá, Maria! Segue um aviso:" in html  # o texto vai em "Ver texto"
    assert f'action="/mensagens/{MENSAGEM_FALHOU}/reenviar"' in html and f'action="/mensagens/{MENSAGEM_FALHOU}/cancelar"' in html
    assert MENSAGEM_PENDENTE not in html and MENSAGEM_ENVIADA not in html  # outros filtros


def test_filtros_aguardando_enviadas_e_todas(cliente, base_whatsapp):
    entrar(cliente)
    pendentes = cliente.get("/mensagens?filtro=pendentes").text
    assert f'action="/mensagens/{MENSAGEM_PENDENTE}/cancelar"' in pendentes and "reenviar" not in pendentes.split("<tbody>")[1]
    assert "CNH perto de vencer, Troca de óleo atrasada" in pendentes and "sai a partir de 06/11/2026 08:00" in pendentes
    enviadas = cliente.get("/mensagens?filtro=enviadas").text
    assert "Enviada" in enviadas and "/cancelar" not in enviadas.split("<tbody>")[1]
    todas = cliente.get("/mensagens?filtro=todas").text
    assert todas.count("<tr data-recolhivel>") == 3
    assert cliente.get("/mensagens?filtro=lixo").text.count("<tr data-recolhivel>") == 1  # filtro inválido volta ao padrão


def test_lista_vazia_orienta(cliente, base_whatsapp):
    base_whatsapp.mensagens.clear()
    entrar(cliente)
    assert "Nenhuma mensagem ainda" in cliente.get("/mensagens").text
    base_whatsapp.mensagens.append({**{"id": MENSAGEM_ENVIADA, "cliente_id": "c", "cliente": "X", "numero": None, "texto": "t", "status": "enviada",
                                       "tentativas": 1, "erro": None, "enviar_apos": None, "criado_em": "2026-11-05T11:00:00+00:00", "tipos": []}})
    html = cliente.get("/mensagens").text  # filtro padrão sem resultados, mas há histórico
    assert "Nada nesta situação" in html and "/mensagens?filtro=todas" in html


def test_cancelar_e_reenviar_voltam_para_a_lista_com_aviso(cliente, base_whatsapp):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    r = cliente.post(f"/mensagens/{MENSAGEM_PENDENTE}/cancelar", data={"csrf_token": token, "voltar_para": "/mensagens?filtro=pendentes"})
    assert r.status_code == 303 and r.headers["location"] == "/mensagens?filtro=pendentes" and base_whatsapp.cancelados == [MENSAGEM_PENDENTE]
    assert "Mensagem cancelada" in cliente.get("/mensagens").text
    r = cliente.post(f"/mensagens/{MENSAGEM_FALHOU}/reenviar", data={"csrf_token": token})
    assert r.status_code == 303 and r.headers["location"] == "/mensagens" and base_whatsapp.reenviados == [MENSAGEM_FALHOU]
    assert "devolvida à fila" in cliente.get("/mensagens").text


def test_destino_de_volta_so_aceita_a_propria_pagina(cliente, base_whatsapp):
    entrar(cliente)
    r = cliente.post(f"/mensagens/{MENSAGEM_PENDENTE}/cancelar", data={"csrf_token": csrf_da_sessao(cliente), "voltar_para": "https://mal.exemplo/x"})
    assert r.headers["location"] == "/mensagens"


def test_mensagem_que_mudou_de_situacao_avisa_sem_quebrar(cliente, base_whatsapp):
    entrar(cliente)
    base_whatsapp.falhar_com = ValueError("Esta mensagem mudou de situação. Atualize a página para ver como ela está.")
    r = cliente.post(f"/mensagens/{MENSAGEM_PENDENTE}/cancelar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert r.status_code == 303
    assert "mudou de situação" in cliente.get("/mensagens").text


def test_id_invalido_e_404_e_sem_csrf_e_recusado(cliente, base_whatsapp):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    assert cliente.post("/mensagens/nao-e-uuid/cancelar", data={"csrf_token": token}).status_code == 404
    assert cliente.post(f"/mensagens/{MENSAGEM_PENDENTE}/cancelar", data={}).status_code in (400, 403)
    assert base_whatsapp.cancelados == []


def test_locatario_nao_acessa(cliente, base_whatsapp):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/mensagens", follow_redirects=False).status_code in (302, 303, 403)
    assert cliente.post(f"/mensagens/{MENSAGEM_PENDENTE}/cancelar", data={"csrf_token": "x"}).status_code in (302, 303, 400, 403)
    assert base_whatsapp.cancelados == []


def test_sem_login_vai_para_o_login(cliente, base_whatsapp):
    r = cliente.get("/mensagens")
    assert r.status_code in (302, 303) and "/login" in r.headers["location"]


def test_menu_tem_mensagens(cliente, base_whatsapp):
    entrar(cliente)
    assert 'href="/mensagens"' in cliente.get("/").text
