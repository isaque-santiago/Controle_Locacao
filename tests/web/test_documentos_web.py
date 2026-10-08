"""Fase 3: Documentos parte A (lista e abertura do comprovante, somente leitura)."""

from tests.web.conftest import entrar

HX = {"HX-Request": "true", "HX-Target": "resultado"}
E1 = "00000000-0000-0000-0000-0000000000e1"
E2 = "00000000-0000-0000-0000-0000000000e2"


def test_lista_mostra_documentos_com_contagem_ordem_e_escapa_dados(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos").text
    assert "2 vencido(s) · 1 a vencer" in html
    assert "Todos <b>5</b>" in html and "Vencido <b>2</b>" in html and "A vencer <b>1</b>" in html and "Em dia <b>2</b>" in html
    assert "IPVA &lt;b&gt;2026&lt;/b&gt;" in html and "<b>2026</b>" not in html
    assert "BRA-2E19" in html and "QRS-4T21" in html and "R$ 150,00" in html and "Licenciamento" in html
    assert "Regularizado" in html and "Vencido" in html
    # vencidos primeiro (o mais antigo antes), depois a vencer, em dia pendente e por fim o regularizado
    assert html.index("IPVA &lt;b&gt;") < html.index("Outro") < html.index("Seguro") < html.index("Licenciamento") < html.rindex("Regularizado")


def test_lista_filtra_por_situacao_e_busca_por_placa(cliente, base_documentos):
    entrar(cliente)
    vencidos = cliente.get("/documentos?situacao=vencido").text
    assert "IPVA" in vencidos and "Licenciamento" not in vencidos and "Seguro" not in vencidos
    assert "Licenciamento" in cliente.get("/documentos?situacao=invalida").text  # situação inválida volta a Todos
    so_m2 = cliente.get("/documentos?q=qrs-4t21").text
    assert "Licenciamento" in so_m2 and "Seguro" not in so_m2
    assert "Nenhum documento encontrado" in cliente.get("/documentos?q=zzz").text
    trecho = cliente.get("/documentos?q=bra", headers=HX).text
    assert "<html" not in trecho and 'class="chips"' in trecho


def test_lista_vazia_e_paginada(cliente, base_documentos):
    entrar(cliente)
    base_documentos.documentos.extend({**base_documentos.documentos[2], "id": f"x{n}"} for n in range(12))
    assert "Mostrando 1 a 10 de 17" in cliente.get("/documentos").text
    assert "Mostrando 11 a 17 de 17" in cliente.get("/documentos?pagina=2").text
    base_documentos.documentos.clear()
    assert "Nenhum documento cadastrado" in cliente.get("/documentos").text


def test_comprovante_so_aparece_quando_anexado_e_abre_pelo_link_assinado(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos").text
    assert html.count("Comprovante</a>") == 1 and f'href="/documentos/{E1}/comprovante"' in html
    assert 'rel="noopener noreferrer"' in html and "Sem comprovante" in html
    resposta = cliente.get(f"/documentos/{E1}/comprovante", follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == base_documentos.url_assinada + "m1/e1/a.pdf?token=x"
    assert resposta.headers["cache-control"] == "no-store"


def test_comprovante_inexistente_sem_arquivo_ou_id_invalido_da_404(cliente, base_documentos):
    entrar(cliente)
    assert cliente.get(f"/documentos/{E2}/comprovante").status_code == 404  # sem comprovante
    assert cliente.get("/documentos/00000000-0000-0000-0000-0000000000ff/comprovante").status_code == 404
    assert cliente.get("/documentos/abc/comprovante").status_code == 404


def test_documentos_exigem_dono(cliente, base_documentos):
    assert cliente.get("/documentos").status_code == 303
    assert cliente.get(f"/documentos/{E1}/comprovante").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/documentos").status_code == 403
    assert cliente.get(f"/documentos/{E1}/comprovante").status_code == 403
