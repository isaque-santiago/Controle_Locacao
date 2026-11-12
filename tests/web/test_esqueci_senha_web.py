"""«Esqueci minha senha» do portal: tela pública que registra o pedido para o dono (CSRF do login, limite por IP, resposta única)."""

from src.domain.pedido_senha import MENSAGEM_PEDIDO
from tests.web.conftest import entrar, extrair_csrf

CPF = "529.982.247-25"


def _abrir(cliente):
    pagina = cliente.get("/login/esqueci-senha")
    assert pagina.status_code == 200
    return extrair_csrf(pagina.text)


def test_login_leva_ao_esqueci_minha_senha(cliente):
    assert 'href="/login/esqueci-senha"' in cliente.get("/login").text


def test_tela_pede_so_o_cpf_e_explica_o_caminho(cliente):
    html = cliente.get("/login/esqueci-senha").text
    assert "Esqueci minha senha" in html and 'name="cpf"' in html and 'name="csrf_token"' in html
    assert 'action="/login/esqueci-senha"' in html and "entrega a você pessoalmente" in html
    assert 'name="senha"' not in html  # nada de senha nesta tela


def test_pedido_valido_registra_so_os_digitos_e_confirma(cliente, servico):
    token = _abrir(cliente)
    resposta = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": CPF})
    assert resposta.status_code == 200 and MENSAGEM_PEDIDO in resposta.text
    assert servico.pedidos_de_senha == ["52998224725"]
    assert 'name="cpf"' not in resposta.text and 'href="/login"' in resposta.text


def test_a_resposta_nao_diz_se_o_cpf_tem_acesso(cliente, servico):
    """O serviço (a RPC) não devolve nada: um CPF qualquer, válido, recebe exatamente a mesma resposta."""
    token = _abrir(cliente)
    a = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": CPF})
    b = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": "111.444.777-35"})
    assert a.status_code == b.status_code == 200 and a.text == b.text


def test_cpf_vazio_ou_invalido_volta_com_erro_e_nao_chama_o_banco(cliente, servico):
    token = _abrir(cliente)
    vazio = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": ""})
    assert vazio.status_code == 400 and "informe o CPF" in vazio.text
    invalido = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": "123.456.789-00"})
    assert invalido.status_code == 400 and "CPF válido" in invalido.text and 'value="123.456.789-00"' in invalido.text
    assert servico.pedidos_de_senha == []


def test_sem_o_token_do_login_o_pedido_e_recusado(cliente, servico):
    cliente.get("/login/esqueci-senha")
    assert cliente.post("/login/esqueci-senha", data={"csrf_token": "errado", "cpf": CPF}).status_code in (400, 403)
    assert cliente.post("/login/esqueci-senha", data={"cpf": CPF}).status_code in (400, 403)
    assert servico.pedidos_de_senha == []


def test_falha_do_servico_mostra_erro_sem_dizer_o_motivo(cliente, servico):
    servico.pedido_recusado = RuntimeError("tabela inexistente")
    token = _abrir(cliente)
    resposta = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": CPF})
    assert resposta.status_code in (500, 503) and "tabela inexistente" not in resposta.text and "Pedido registrado" not in resposta.text


def test_pedidos_demais_do_mesmo_ip_sao_bloqueados(cliente, servico):
    token = _abrir(cliente)
    for _ in range(20):
        assert cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": CPF}).status_code == 200
    bloqueado = cliente.post("/login/esqueci-senha", data={"csrf_token": token, "cpf": CPF})
    assert bloqueado.status_code == 429 and "Muitos pedidos" in bloqueado.text and int(bloqueado.headers["Retry-After"]) > 0
    assert len(servico.pedidos_de_senha) == 20


def test_quem_ja_entrou_vai_para_o_inicio(cliente):
    entrar(cliente)
    resposta = cliente.get("/login/esqueci-senha")
    assert resposta.status_code == 303 and resposta.headers["location"] == "/"
