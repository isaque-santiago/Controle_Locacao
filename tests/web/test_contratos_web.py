"""Fase 3: lista e ficha de Contratos no app FastAPI."""

from tests.web.conftest import entrar

HX = {"HX-Request": "true", "HX-Target": "resultado"}


def test_lista_abre_nos_ativos_e_escapa_dados(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get("/contratos").text
    assert "1 contrato ativo" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html
    assert "BRA-2E19" in html and "Semanal" in html and "R$ 280,00" in html and "01/08/2026" in html
    assert "Mensal" not in html  # o encerrado só aparece no filtro certo
    assert f"/contratos/{base_contratos.id}" in html


def test_lista_filtra_por_situacao_e_busca(cliente, base_contratos):
    entrar(cliente)
    assert "Mensal" in cliente.get("/contratos?status=encerrado").text
    todos = cliente.get("/contratos?status=todos").text
    assert "Semanal" in todos and "Mensal" in todos
    assert "Maria" in cliente.get("/contratos?status=todos&q=bra2e19").text
    assert "Maria" in cliente.get("/contratos?status=todos&q=BRA-2E19").text
    assert "Nenhum contrato encontrado" in cliente.get("/contratos?q=zzz").text
    assert "Maria" in cliente.get("/contratos?status=invalido").text  # situação inválida volta ao padrão
    trecho = cliente.get("/contratos?q=maria", headers=HX).text
    assert "<html" not in trecho and 'class="chips"' in trecho


def test_lista_conta_por_situacao(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get("/contratos").text
    assert "Ativo <b>1</b>" in html and "Encerrado <b>1</b>" in html and "Cancelado <b>0</b>" in html and "Todos <b>2</b>" in html


def test_ficha_mostra_faixa_de_dados_e_cobrancas(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Maria &lt;b&gt;Silva&lt;/b&gt;" in html and "CG 160" in html and "BRA-2E19" in html
    assert "R$ 280,00" in html and "R$ 400,00" in html and "10.500 km" in html
    assert "Indeterminado" in html and "20/10/2026" in html
    assert "Atrasada" in html and "Paga" in html and "01/08/2026" in html
    assert 'href="/clientes/' + base_contratos.cliente["id"] in html


def test_ficha_abas_vistorias_e_manutencoes(cliente, base_contratos):
    entrar(cliente)
    base = f"/contratos/{base_contratos.id}"
    vistorias = cliente.get(f"{base}?aba=vistorias").text
    assert "Entrega" in vistorias and "Cheio" in vistorias and "freio dianteiro, espelho retrovisor" in vistorias
    assert "Ainda não realizada — será registrada no encerramento do contrato" in vistorias
    manutencoes = cliente.get(f"{base}/abas/manutencoes").text
    assert "<html" not in manutencoes and "Óleo &lt;i&gt;e filtro&lt;/i&gt;" in manutencoes
    assert "Antes do contrato" not in manutencoes  # fora da vigência do contrato


def test_ficha_com_prazo_definido_e_contrato_inexistente(cliente, base_contratos):
    entrar(cliente)
    encerrado = cliente.get("/contratos/00000000-0000-0000-0000-0000000000d2").text
    assert "30/06/2026" in encerrado and "Encerrado · desde 01/01/2026" in encerrado
    assert cliente.get("/contratos/00000000-0000-0000-0000-0000000000ff").status_code == 404
    assert cliente.get("/contratos/abc").status_code == 404
    assert cliente.get(f"/contratos/{base_contratos.id}/abas/inexistente").status_code == 404


def test_contratos_exigem_dono(cliente, base_contratos):
    assert cliente.get("/contratos").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/contratos").status_code == 403
    assert cliente.get(f"/contratos/{base_contratos.id}").status_code == 403


def test_tipo_da_cobranca_aparece_com_acento_na_ficha_do_contrato_e_do_cliente(cliente, base_contratos, base_clientes):
    entrar(cliente)
    contrato = cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Caução" in contrato and "Locação" in contrato and "Caucao" not in contrato
    base_clientes.cobrancas[0]["tipo"] = "multa_transito"
    assert "Multa de trânsito" in cliente.get(f"/clientes/{base_clientes.id}?aba=pagamentos").text
