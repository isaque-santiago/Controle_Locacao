"""Aba WhatsApp da ficha do cliente: histórico, parar e voltar a enviar mensagens (só o dono)."""

from tests.web.conftest import csrf_da_sessao, entrar


def _cabecalhos(cliente):
    return {"HX-Request": "true", "X-CSRF-Token": csrf_da_sessao(cliente)}


def test_ha_a_aba_whatsapp_na_ficha(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}").text
    assert 'id="aba-whatsapp"' in html and ">WhatsApp<" in html


def test_aba_mostra_o_numero_o_historico_e_oferece_parar(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert "Mensagens automáticas de WhatsApp" in html and "(11) 98765-4321" in html
    assert "Histórico de mensagens" in html and html.count("<tr data-recolhivel>") == 3
    assert "A Evolution recusou o pedido (400)." in html and "Aguardando envio" in html and "Enviada" in html
    assert f'hx-post="/clientes/{base_clientes.id}/whatsapp/bloquear"' in html and "Parar mensagens deste cliente" in html
    assert "Só você pode parar as mensagens de um cliente" in html
    parcial = cliente.get(f"/clientes/{base_clientes.id}/abas/whatsapp").text
    assert "Histórico de mensagens" in parcial and 'hx-swap-oob="true"' in parcial


def test_cliente_sem_whatsapp_cadastrado_avisa(cliente, base_clientes):
    base_clientes.clientes[0]["whatsapp"] = None
    entrar(cliente)
    assert "não tem WhatsApp cadastrado" in cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text


def test_historico_vazio(cliente, base_clientes, base_whatsapp):
    base_whatsapp.mensagens.clear()
    entrar(cliente)
    assert "Nenhuma mensagem enviada" in cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text


def test_parar_grava_o_motivo_e_volta_para_a_aba(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/bloquear", data={"motivo": "  Pediu ao dono "}, headers=_cabecalhos(cliente))
    assert r.status_code == 200 and r.headers["HX-Redirect"] == f"/clientes/{base_clientes.id}?aba=whatsapp"
    assert base_whatsapp.bloqueios == [(base_clientes.id, "Pediu ao dono")]
    assert "não receberá mais mensagens automáticas" in cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text


def test_parar_sem_motivo_mostra_o_erro_no_campo(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/bloquear", data={"motivo": "ab"}, headers=_cabecalhos(cliente))
    assert r.status_code == 422 and "Motivo: explique por que este cliente não deve receber mensagens" in r.text
    assert base_whatsapp.bloqueios == [] and "Cache-Control" in r.headers and r.headers["Cache-Control"] == "no-store"


def test_cliente_parado_mostra_o_motivo_e_oferece_voltar(cliente, base_clientes, base_whatsapp):
    base_clientes.clientes[0].update(nao_enviar_whatsapp=True, motivo_bloqueio_whatsapp="Pediu ao dono",
                                     bloqueio_whatsapp_em="2026-11-06T17:35:00+00:00")
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert "não recebe as mensagens automáticas desde 06/11/2026 14:35" in html and "Motivo: Pediu ao dono" in html
    assert f'hx-post="/clientes/{base_clientes.id}/whatsapp/liberar"' in html and "Parar mensagens deste cliente" not in html
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/liberar", headers=_cabecalhos(cliente))
    assert r.headers["HX-Redirect"] == f"/clientes/{base_clientes.id}?aba=whatsapp" and base_whatsapp.desbloqueios == [base_clientes.id]
    assert "voltou a receber mensagens automáticas" in cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text


def test_falha_ao_gravar_avisa_sem_derrubar(cliente, base_clientes, base_whatsapp):
    base_whatsapp.falhar_com = RuntimeError("banco fora")
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/bloquear", data={"motivo": "Pediu ao dono"}, headers=_cabecalhos(cliente))
    assert r.status_code == 200 and "HX-Redirect" in r.headers


def test_historico_que_falha_ao_carregar_nao_derruba_a_ficha(cliente, base_clientes, monkeypatch):
    from src.web import dados_whatsapp

    def quebra(*a, **k):
        raise RuntimeError("tabela inexistente")

    monkeypatch.setattr(dados_whatsapp.whatsapp_painel, "listar_do_cliente", quebra, raising=False)
    entrar(cliente)
    r = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp")
    assert r.status_code == 200 and "Não foi possível carregar o histórico de mensagens" in r.text


def test_locatario_e_cliente_sem_login_nao_agem(cliente, base_clientes, base_whatsapp):
    assert cliente.post(f"/clientes/{base_clientes.id}/whatsapp/bloquear", data={"motivo": "xyz"}).status_code in (302, 303, 400, 403)
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/liberar", headers={"HX-Request": "true"})
    assert r.status_code in (302, 303, 400, 403) and base_whatsapp.bloqueios == [] and base_whatsapp.desbloqueios == []
