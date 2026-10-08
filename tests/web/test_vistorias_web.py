"""Fase 3: Vistorias parte A (lista e comparação, somente leitura)."""

from tests.web.conftest import entrar

HX = {"HX-Request": "true", "HX-Target": "resultado"}
CONTRATO = "00000000-0000-0000-0000-0000000000d1"


def test_lista_mostra_vistorias_com_contagem_e_escapa_dados(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get("/vistorias").text
    assert "Maria &lt;b&gt;Silva&lt;/b&gt;" in html and "BRA-2E19" in html
    assert "Todas <b>3</b>" in html and "Entrega <b>2</b>" in html and "Devolução <b>1</b>" in html
    assert "10.500 km" in html and "Cheio" in html and "Risco no tanque" in html
    assert "freio dianteiro" not in html and "Freio dianteiro" in html  # avaria da devolução, com rótulo
    assert f"/vistorias/contrato/{CONTRATO}" in html
    assert html.index("01/09/2026") < html.index("01/08/2026") < html.index("01/01/2026")  # mais recente primeiro


def test_lista_filtra_por_tipo_e_busca(cliente, base_vistorias):
    entrar(cliente)
    devolucoes = cliente.get("/vistorias?tipo=devolucao").text
    assert "01/09/2026" in devolucoes and "01/08/2026" not in devolucoes
    assert "01/08/2026" in cliente.get("/vistorias?tipo=invalido").text  # tipo inválido volta a Todas
    assert "01/08/2026" in cliente.get("/vistorias?q=bra2e19").text
    assert "Nenhuma vistoria encontrada" in cliente.get("/vistorias?q=zzz").text
    trecho = cliente.get("/vistorias?q=maria", headers=HX).text
    assert "<html" not in trecho and 'class="chips"' in trecho


def test_lista_vazia_e_paginada(cliente, base_vistorias):
    entrar(cliente)
    base_vistorias.registradas.extend(
        {**base_vistorias.antiga, "id": f"x{n}", "data": f"2025-01-{n:02d}"} for n in range(1, 16))
    pagina_1 = cliente.get("/vistorias").text
    assert "Mostrando 1 a 10 de 18" in pagina_1 and "pagina=2" in pagina_1
    assert "Mostrando 11 a 18 de 18" in cliente.get("/vistorias?pagina=2").text
    base_vistorias.registradas.clear()
    assert "Nenhuma vistoria registrada" in cliente.get("/vistorias").text


def test_comparacao_mostra_dois_cartoes_fotos_e_alterados(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get(f"/vistorias/contrato/{CONTRATO}").text
    assert "Maria &lt;b&gt;Silva&lt;/b&gt;" in html and "CG 160" in html and "em andamento" in html
    assert "500 km" in html and "1 registrada(s)" in html  # só o freio é avaria; o item ausente não conta
    assert "Rack &lt;i&gt;extra&lt;/i&gt;" in html and "<i>extra</i>" not in html
    assert html.count("alterado</span>") == 4  # 2 itens, marcados nos dois cartões and "mudaram entre a entrega e a devolução" in html
    assert 'src="https://projeto.supabase.co/assinada/v1/a.jpg?token=x"' in html
    assert 'rel="noopener noreferrer"' in html and "Lado &lt;direito&gt;" in html
    assert "Foto indisponível" in html and "Nenhuma foto anexada" in html


def test_comparacao_sem_devolucao_mostra_cartao_vazio(cliente, base_vistorias):
    entrar(cliente)
    base_vistorias.registradas.remove(base_vistorias.devolucao)
    html = cliente.get(f"/vistorias/contrato/{CONTRATO}").text
    assert "Ainda não realizada — será registrada no encerramento do contrato" in html
    assert "mudaram entre a entrega e a devolução" not in html


def test_comparacao_contrato_inexistente_e_acesso(cliente, base_vistorias):
    entrar(cliente)
    assert cliente.get("/vistorias/contrato/00000000-0000-0000-0000-0000000000ff").status_code == 404
    assert cliente.get("/vistorias/contrato/abc").status_code == 404


def test_vistorias_exigem_dono(cliente, base_vistorias):
    assert cliente.get("/vistorias").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/vistorias").status_code == 403
    assert cliente.get(f"/vistorias/contrato/{CONTRATO}").status_code == 403


def test_csp_libera_imagens_so_da_origem_do_storage(cliente, monkeypatch):
    from src.web import seguranca

    monkeypatch.setattr("src.config.get_supabase_url", lambda: "https://projeto.supabase.co")
    seguranca.politica_de_conteudo.cache_clear()
    try:
        csp = cliente.get("/login").headers["Content-Security-Policy"]
        assert "img-src 'self' data: https://projeto.supabase.co;" in csp
        assert "'unsafe-inline'" not in csp
    finally:
        seguranca.politica_de_conteudo.cache_clear()
