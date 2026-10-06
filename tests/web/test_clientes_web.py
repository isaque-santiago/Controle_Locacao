"""Fase 3: lista, ficha e formulários de Clientes no app FastAPI."""

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true", "HX-Target": "resultado"}


def test_lista_filtra_busca_e_escapa_dados(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get("/clientes").text
    assert "1 cliente cadastrado" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html
    assert "***.982.***-**" in html and "BRA-2E19" in html
    assert "Maria" not in cliente.get("/clientes?status=inativo").text
    assert "Maria" in cliente.get("/clientes?q=529.982").text
    trecho = cliente.get("/clientes?q=maria", headers=HX).text
    assert "<html" not in trecho and 'class="chips"' in trecho


def test_ficha_tem_abas_e_dados_financeiros(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}").text
    assert "Dados pessoais" in html and "R$ 100,00" in html
    contratos = cliente.get(f"/clientes/{base_clientes.id}?aba=contratos").text
    assert "BRA-2E19" in contratos and "R$ 300,00" in contratos


def test_cadastro_valida_e_grava(cliente, base_clientes, acoes_clientes_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    invalido = cliente.post("/clientes/novo", data={"csrf_token": token, "nome": "", "cpf": "123"}, headers={"HX-Request": "true"})
    assert invalido.status_code == 422 and "CPF: informe um CPF válido" in invalido.text
    resposta = cliente.post("/clientes/novo", data={"csrf_token": token, "nome": "Ana", "cpf": "529.982.247-25", "status": "ativo"}, headers={"HX-Request": "true"})
    assert resposta.headers["HX-Redirect"] == f"/clientes/{base_clientes.id}"
    assert acoes_clientes_falsas[0][0] == "criar"


def test_rotas_de_clientes_exigem_dono(cliente, base_clientes):
    assert cliente.get("/clientes").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/clientes").status_code == 403
    assert cliente.get(f"/clientes/{base_clientes.id}").status_code == 403
