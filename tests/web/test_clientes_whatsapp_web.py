"""Aba WhatsApp da ficha do cliente: histórico, parar e voltar a enviar mensagens (só o dono)."""

from tests.web.conftest import csrf_da_sessao, entrar


def _cabecalhos(cliente):
    return {"HX-Request": "true", "X-CSRF-Token": csrf_da_sessao(cliente)}


def test_ha_a_aba_whatsapp_na_ficha(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}").text
    assert 'id="aba-whatsapp"' in html and ">WhatsApp<" in html


def test_aba_mostra_o_historico_e_oferece_parar(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert "Mensagens automáticas de WhatsApp" in html and "nenhuma cobrança nem recibo automático" in html
    assert "Histórico de mensagens" in html and html.count("<tr data-recolhivel>") == 3
    assert "A Evolution recusou o pedido (400)." in html and "Aguardando envio" in html and "Enviada" in html
    assert f'hx-post="/clientes/{base_clientes.id}/whatsapp/bloquear"' in html and "Parar mensagens deste cliente" in html
    assert "Só você pode parar as mensagens de um cliente" in html
    parcial = cliente.get(f"/clientes/{base_clientes.id}/abas/whatsapp").text
    assert "Histórico de mensagens" in parcial and 'hx-swap-oob="true"' in parcial


GRUPO_MARIA = "120363025246125486@g.us"


def test_cliente_sem_grupo_avisa_e_oferece_a_lista(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert "não tem grupo de WhatsApp cadastrado" in html and "ficam ignoradas" in html
    assert f'hx-post="/clientes/{base_clientes.id}/whatsapp/grupo"' in html
    assert "— sem grupo —" in html and "Maria Souza - ABC1D23 (4 participantes)" in html and "Carlos Lima - XYZ9A99 (3 participantes)" in html
    assert 'name="grupo_id"' in html and "termina em @g.us" in html


def test_cliente_com_grupo_mostra_o_nome_e_deixa_o_grupo_selecionado(cliente, base_clientes):
    base_clientes.clientes[0]["whatsapp_grupo_id"] = GRUPO_MARIA
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert "vão para o grupo <strong>Maria Souza - ABC1D23</strong>" in html and "não tem grupo de WhatsApp" not in html
    assert f'<option value="{GRUPO_MARIA}" selected>' in html


def test_grupo_atual_fora_da_lista_nao_some_do_formulario(cliente, base_clientes, base_whatsapp):
    base_clientes.clientes[0]["whatsapp_grupo_id"] = "120363999999999999@g.us"
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert "fora da lista" in html and '<option value="120363999999999999@g.us" selected>' in html


def test_lista_de_grupos_que_falha_nao_derruba_a_ficha(cliente, base_clientes, monkeypatch):
    from src.web import dados_whatsapp
    monkeypatch.setattr(dados_whatsapp, "grupos", lambda: (_ for _ in ()).throw(RuntimeError("tabela inexistente")))
    entrar(cliente)
    resposta = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp")
    assert resposta.status_code == 200 and "Histórico de mensagens" in resposta.text and "tabela inexistente" not in resposta.text


def test_salvar_grupo_escolhido_na_lista(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/grupo", data={"grupo_escolhido": GRUPO_MARIA, "grupo_id": ""}, headers=_cabecalhos(cliente))
    assert r.status_code == 200 and r.headers["HX-Redirect"] == f"/clientes/{base_clientes.id}?aba=whatsapp"
    assert base_whatsapp.grupos_definidos == [(base_clientes.id, GRUPO_MARIA)]
    assert "Grupo de WhatsApp de" in cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text


def test_id_colado_tem_prioridade_e_e_normalizado(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    cliente.post(f"/clientes/{base_clientes.id}/whatsapp/grupo",
                 data={"grupo_escolhido": GRUPO_MARIA, "grupo_id": " 120363111111111111@G.US "}, headers=_cabecalhos(cliente))
    assert base_whatsapp.grupos_definidos == [(base_clientes.id, "120363111111111111@g.us")]


def test_sem_grupo_remove_e_avisa(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    cliente.post(f"/clientes/{base_clientes.id}/whatsapp/grupo", data={"grupo_escolhido": "", "grupo_id": ""}, headers=_cabecalhos(cliente))
    assert base_whatsapp.grupos_definidos == [(base_clientes.id, None)]
    assert "removido" in cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text


def test_id_invalido_mostra_o_erro_no_campo_e_nao_grava(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/grupo", data={"grupo_id": "5511988887777"}, headers=_cabecalhos(cliente))
    assert r.status_code == 422 and "ID de grupo inválido" in r.text and "5511988887777" in r.text
    assert base_whatsapp.grupos_definidos == [] and r.headers["Cache-Control"] == "no-store"


def test_grupo_ja_usado_por_outro_cliente_mostra_o_erro(cliente, base_clientes, base_whatsapp):
    base_whatsapp.falhar_com = ValueError("Este grupo já está ligado a outro cliente.")
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/grupo", data={"grupo_escolhido": GRUPO_MARIA}, headers=_cabecalhos(cliente))
    assert r.status_code == 422 and "já está ligado a outro cliente" in r.text


def test_salvar_grupo_exige_csrf(cliente, base_clientes, base_whatsapp):
    entrar(cliente)
    r = cliente.post(f"/clientes/{base_clientes.id}/whatsapp/grupo", data={"grupo_escolhido": GRUPO_MARIA}, headers={"HX-Request": "true"})
    assert r.status_code == 403 and base_whatsapp.grupos_definidos == []


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


def test_ha_caixa_de_busca_ligada_a_lista_de_grupos(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=whatsapp").text
    assert 'id="wa-grupo-busca"' in html and "Buscar grupo (nome, sobrenome ou placa)" in html
    assert 'data-filtrar-opcoes="wa-grupo-escolhido"' in html and 'data-filtrar-aviso="wa-grupo-contagem"' in html
    assert 'id="wa-grupo-escolhido"' in html and 'id="wa-grupo-contagem"' in html and 'aria-live="polite"' in html
    # a lista fica aberta (8 linhas) e a contagem já diz quantos grupos há
    assert 'class="entrada lista-aberta"' in html and 'size="8"' in html and "2 grupos na lista" in html
    # o campo de busca não tem name: não vai no formulário nem sobrescreve o grupo escolhido
    trecho = html[html.index('id="wa-grupo-busca"'):]
    assert "name=" not in trecho[:trecho.index(">")]


def test_o_javascript_traz_o_filtro_de_opcoes():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[2] / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "data-filtrar-opcoes" in js and "filtrarOpcoes" in js and "normalize('NFD')" in js
    assert "PALAVRAS_FRACAS" in js and "replace(/[^a-z0-9]/g, '')" in js  # placa sem hífen e palavras fracas ("de", "la") ignoradas
    assert "e.key === 'Enter'" in js or "ev.key === 'Enter'" in js or "key === 'Enter' && e.target.matches" in js
