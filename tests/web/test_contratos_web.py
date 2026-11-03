"""Fase 3: lista e ficha de Contratos no app FastAPI."""

from decimal import Decimal

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
    assert "<html" not in trecho and 'class="chips filtro-opcoes"' in trecho


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
    assert 'class="cartao vistoria-resumo"' in vistorias and 'class="vistoria-dados"' in vistorias
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


def test_lista_ordena_pela_coluna_na_url(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get("/contratos?status=todos&ordem=-valor").text
    assert 'aria-sort="descending"' in html and 'href="/contratos?status=todos"' in html  # terceiro clique volta ao padrão
    assert 'name="ordem" value="-valor"' in html


def test_contrato_em_pdf_baixa_o_arquivo_com_as_motos_do_contrato(cliente, base_contratos, monkeypatch):
    from src.web import dados_contratos

    chamadas = []
    monkeypatch.setattr(dados_contratos.contrato_pdf, "gerar", lambda c, cl, motos: chamadas.append((c, cl, motos)) or b"%PDF-1.4 falso")
    entrar(cliente)
    resposta = cliente.get(f"/contratos/{base_contratos.id}/pdf")
    assert resposta.status_code == 200 and resposta.content == b"%PDF-1.4 falso"
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.headers["content-disposition"] == 'attachment; filename="contrato_BRA2E19_2026-08-01.pdf"'
    contrato, cliente_pdf, motos = chamadas[0]
    assert contrato["id"] == base_contratos.id and cliente_pdf["id"] == base_contratos.cliente["id"]
    assert [m["placa"] for m in motos] == ["BRA2E19", "QRS4T21"]


def test_ficha_oferece_o_pdf_e_a_geracao_exige_dono(cliente, base_contratos):
    entrar(cliente)
    assert f'href="/contratos/{base_contratos.id}/pdf"' in cliente.get(f"/contratos/{base_contratos.id}").text
    assert cliente.get("/contratos/00000000-0000-0000-0000-00000000ffff/pdf").status_code == 404
    cliente.cookies.clear()
    assert cliente.get(f"/contratos/{base_contratos.id}/pdf").status_code == 303


def test_lista_mostra_motos_vinculadas_e_promessa(cliente, base_contratos):
    entrar(cliente)
    base_contratos.vinculadas = {base_contratos.id: 2}
    base_contratos.contratos[0]["tipo_contrato"] = "promessa_compra"
    html = cliente.get("/contratos").text
    assert "+2 motos" in html and "Promessa de compra" in html


def test_ficha_de_promessa_mostra_totais_e_motos_do_contrato(cliente, base_contratos):
    entrar(cliente)
    base_contratos.contratos[0].update(tipo_contrato="promessa_compra", numero_parcelas=10, parcelas_pagas_inicial=3,
                                       valor_total=Decimal("3800"), valor_entrada=Decimal("1000"))
    html = cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Total da promessa" in html and "R$ 3.800,00" in html and "3 de 10" in html and "Parcelas restantes" in html
    assert "Também neste contrato" in html and "QRS-4T21" in html  # a vinculada da fixture


def test_ficha_de_locacao_comum_nao_mostra_bloco_de_promessa(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Total da promessa" not in html and "Promessa de compra" not in html
