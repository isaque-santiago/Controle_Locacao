"""Fase 3: cadastro e edição do catálogo de manutenção."""

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _dados(token, **extra):
    return {"csrf_token": token, "nome": "Pastilha de freio", "intervalo_km": "5000",
            "intervalo_minimo_km": "3000", "intervalo_dias": "0", "ativo": "on", **extra}


def test_catalogo_oferece_novo_e_edicao_com_dialogo(cliente, base_manutencao):
    entrar(cliente)
    html = cliente.get("/manutencao?aba=catalogo").text
    assert 'hx-get="/manutencao/catalogo/novo"' in html
    assert 'hx-get="/manutencao/catalogo/i1/editar"' in html and 'aria-label="Editar o item Kit de tração"' in html
    novo = cliente.get("/manutencao/catalogo/novo", headers=HX).text
    assert "<html" not in novo and "Novo item do catálogo" in novo and 'name="ativo" checked' in novo
    editar = cliente.get("/manutencao/catalogo/i1/editar", headers=HX).text
    assert "Editar item do catálogo" in editar and 'value="Kit de tração"' in editar and 'value="3000"' in editar
    pagina = cliente.get("/manutencao/catalogo/i1/editar").text
    assert "<html" in pagina and "Voltar para o catálogo" in pagina


def test_criar_item_grava_e_redireciona_com_aviso(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    resposta = cliente.post("/manutencao/catalogo/novo", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == "/manutencao?aba=catalogo"
    assert acoes_manutencao_falsas.itens_criados == [{"nome": "Pastilha de freio", "intervalo_km": 5000,
        "intervalo_minimo_km": 3000, "intervalo_dias": None, "ativo": True}]
    assert "Pastilha de freio" in cliente.get("/manutencao?aba=catalogo").text


def test_editar_item_pode_inativar_e_redireciona_sem_htmx(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    dados = _dados(csrf_da_sessao(cliente), nome="Kit revisado")
    dados.pop("ativo")
    resposta = cliente.post("/manutencao/catalogo/i1/editar", data=dados)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/manutencao?aba=catalogo"
    assert acoes_manutencao_falsas.itens_atualizados[0][0] == "i1"
    assert acoes_manutencao_falsas.itens_atualizados[0][1]["ativo"] is False


def test_erros_por_campo_preservam_formulario_e_servico_nao_e_chamado(cliente, base_manutencao, acoes_manutencao_falsas):
    entrar(cliente)
    resposta = cliente.post("/manutencao/catalogo/novo", data=_dados(
        csrf_da_sessao(cliente), nome="", intervalo_km="0", intervalo_minimo_km="100", intervalo_dias="0"
    ), headers=HX)
    assert resposta.status_code == 422 and "Corrija os campos destacados" in resposta.text
    assert "Nome: informe" in resposta.text and "informe também o intervalo em km" in resposta.text
    assert acoes_manutencao_falsas.itens_criados == []


def test_item_inexistente_erro_servico_papel_e_csrf(cliente, base_manutencao, acoes_manutencao_falsas):
    assert cliente.get("/manutencao/catalogo/novo").status_code == 303
    entrar(cliente)
    assert cliente.get("/manutencao/catalogo/inexistente/editar").status_code == 404
    assert cliente.post("/manutencao/catalogo/novo", data=_dados("")).status_code in (400, 403)
    acoes_manutencao_falsas.falhar_com = ValueError("Nome já cadastrado.")
    falha = cliente.post("/manutencao/catalogo/novo", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert falha.status_code == 422 and "Nome já cadastrado" in falha.text
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/manutencao/catalogo/novo").status_code == 403
