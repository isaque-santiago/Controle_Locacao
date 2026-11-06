"""Configurações: controles do envio automático de WhatsApp (liga/desliga, modo teste, número de teste, máximo de avisos)."""

from tests.web.conftest import csrf_da_sessao, entrar


def _dados(token, **extra):
    return {"csrf_token": token, "modo": "teste", "numero_teste": "(11) 98888-7777", "max_repeticoes": "10", **extra}


def test_secao_aparece_desligada_e_em_modo_teste_por_padrao(cliente, base_configuracoes):
    entrar(cliente)
    html = cliente.get("/configuracoes").text
    assert 'id="cfg-whatsapp"' in html and "Envio automático por WhatsApp" in html
    assert 'action="/configuracoes/whatsapp"' in html and "Instância do WhatsApp: <strong>ainda sem rodada</strong>" in html
    assert 'id="zap-ativo" name="ativo"' in html and 'id="zap-ativo" name="ativo" checked' not in html
    assert 'value="teste" checked' in html and 'value="real" checked' not in html
    assert 'id="zap-max" name="max_repeticoes" type="text" value="10"' in html


def test_mostra_o_estado_da_ultima_rodada(cliente, base_configuracoes):
    base_configuracoes.config.update(whatsapp_ativo=True, whatsapp_modo_teste=False, whatsapp_ultimo_estado="close",
                                     whatsapp_ultima_rodada_em="2026-11-06T17:35:00+00:00", whatsapp_numero_teste="5511988887777")
    entrar(cliente)
    html = cliente.get("/configuracoes").text
    assert "desconectada (leia o QR code na Evolution)" in html and "06/11/2026 14:35" in html
    assert 'value="real" checked' in html and 'value="(11) 98888-7777"' in html


def test_ligar_em_modo_teste_grava_e_avisa(cliente, base_whatsapp):
    entrar(cliente)
    r = cliente.post("/configuracoes/whatsapp", data=_dados(csrf_da_sessao(cliente), ativo="on"))
    assert r.status_code == 303 and r.headers["location"] == "/configuracoes#cfg-whatsapp"
    assert base_whatsapp.controles == [{"whatsapp_ativo": True, "whatsapp_modo_teste": True,
                                        "whatsapp_numero_teste": "5511988887777", "whatsapp_max_repeticoes": 10}]
    assert "Envio ligado em modo teste" in cliente.get("/configuracoes").text


def test_ligar_para_os_clientes_exige_confirmacao(cliente, base_whatsapp):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    r = cliente.post("/configuracoes/whatsapp", data=_dados(token, ativo="on", modo="real"))
    assert r.status_code == 422 and "Confirme que entendeu" in r.text and "Corrija os campos destacados." in r.text
    assert base_whatsapp.controles == []
    r = cliente.post("/configuracoes/whatsapp", data=_dados(token, ativo="on", modo="real", confirmo="on"))
    assert r.status_code == 303 and base_whatsapp.controles[0]["whatsapp_modo_teste"] is False
    assert "as mensagens vão para os clientes" in cliente.get("/configuracoes").text


def test_desligar_nao_exige_numero(cliente, base_whatsapp):
    entrar(cliente)
    r = cliente.post("/configuracoes/whatsapp", data={"csrf_token": csrf_da_sessao(cliente), "modo": "teste", "max_repeticoes": "10"})
    assert r.status_code == 303 and base_whatsapp.controles[0]["whatsapp_ativo"] is False
    assert "desligado" in cliente.get("/configuracoes").text


def test_modo_teste_ligado_sem_numero_mostra_o_erro_e_preserva_o_digitado(cliente, base_whatsapp):
    entrar(cliente)
    r = cliente.post("/configuracoes/whatsapp", data=_dados(csrf_da_sessao(cliente), ativo="on", numero_teste="", max_repeticoes="7"))
    assert r.status_code == 422 and "Número de teste: informe o seu celular" in r.text and 'value="7"' in r.text
    assert 'id="zap-ativo" name="ativo" checked' in r.text  # o que foi marcado continua marcado
    assert base_whatsapp.controles == []


def test_numero_e_maximo_invalidos(cliente, base_whatsapp):
    entrar(cliente)
    r = cliente.post("/configuracoes/whatsapp", data=_dados(csrf_da_sessao(cliente), numero_teste="123", max_repeticoes="0"))
    assert r.status_code == 422 and "por exemplo (11) 98888-7777" in r.text and "Máximo de avisos por assunto" in r.text


def test_falha_ao_gravar_mostra_aviso_na_secao(cliente, base_whatsapp):
    base_whatsapp.falhar_com = ValueError("Controles em uso por outra operação.")
    entrar(cliente)
    r = cliente.post("/configuracoes/whatsapp", data=_dados(csrf_da_sessao(cliente)))
    assert r.status_code == 422 and "Controles em uso por outra operação." in r.text


def test_sem_csrf_e_locatario_sao_recusados(cliente, base_whatsapp):
    entrar(cliente)
    assert cliente.post("/configuracoes/whatsapp", data={"modo": "teste"}).status_code in (400, 403)
    cliente.cookies.clear()
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.post("/configuracoes/whatsapp", data=_dados("x")).status_code in (302, 303, 400, 403)
    assert base_whatsapp.controles == []
