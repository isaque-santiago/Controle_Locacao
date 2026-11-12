"""Aba Portal da ficha: pedido de senha nova do locatário (aviso e botão para descartar). Só o dono."""

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _com_acesso(base, pedido=True):
    base.clientes[0]["auth_user_id"] = "u1"
    base.pedido_senha = {"id": "p1", "pedido_em": "2026-11-10T13:00:00+00:00"} if pedido else None


def test_sem_pedido_a_aba_nao_mostra_aviso(cliente, base_clientes):
    _com_acesso(base_clientes, pedido=False)
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=portal").text
    assert "Pedido de senha nova" not in html and "Descartar pedido" not in html and "Gerar nova senha" in html


def test_pedido_aberto_aparece_com_a_data_e_o_botao_de_descartar(cliente, base_clientes):
    _com_acesso(base_clientes)
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=portal").text
    assert "Pedido de senha nova." in html and "10/11/2026" in html and "Gerar nova senha" in html
    assert f'hx-post="/clientes/{base_clientes.id}/portal/pedido-senha/dispensar"' in html and "Descartar pedido" in html


def test_descartar_chama_a_acao_e_devolve_a_aba(cliente, base_clientes, acoes_clientes_falsas):
    _com_acesso(base_clientes)
    entrar(cliente)
    resposta = cliente.post(f"/clientes/{base_clientes.id}/portal/pedido-senha/dispensar", headers={**HX, "X-CSRF-Token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 200 and 'id="painel-aba"' in resposta.text
    assert ("dispensar_pedido_senha", base_clientes.id) in acoes_clientes_falsas


def test_falha_ao_descartar_mostra_o_erro_na_aba(cliente, base_clientes, monkeypatch):
    from src.web import acoes_clientes

    def falhar(cliente_id):
        raise ValueError("Não foi possível descartar o pedido.")

    monkeypatch.setattr(acoes_clientes, "dispensar_pedido_senha", falhar)
    _com_acesso(base_clientes)
    entrar(cliente)
    resposta = cliente.post(f"/clientes/{base_clientes.id}/portal/pedido-senha/dispensar", headers={**HX, "X-CSRF-Token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 422 and "Não foi possível descartar o pedido." in resposta.text


def test_descartar_exige_dono_e_csrf(cliente, base_clientes, acoes_clientes_falsas):
    caminho = f"/clientes/{base_clientes.id}/portal/pedido-senha/dispensar"
    assert cliente.post(caminho, headers=HX).status_code in (303, 401, 403)
    entrar(cliente)
    assert cliente.post(caminho, headers=HX).status_code in (400, 403)
    assert cliente.post("/clientes/inexistente/portal/pedido-senha/dispensar", headers={**HX, "X-CSRF-Token": csrf_da_sessao(cliente)}).status_code == 404
    assert ("dispensar_pedido_senha", base_clientes.id) not in acoes_clientes_falsas
