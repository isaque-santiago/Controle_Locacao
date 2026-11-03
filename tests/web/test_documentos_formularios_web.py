"""Fase 3: Documentos parte B (novo e editar documento, com comprovante, em diálogo e em página)."""

from types import SimpleNamespace

import pytest

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}
E1 = "00000000-0000-0000-0000-0000000000e1"
E2 = "00000000-0000-0000-0000-0000000000e2"
PDF = b"%PDF-1.7" + b"0" * 64


class ServicoFalso:
    def __init__(self, base):
        self.base = base
        self.criados, self.atualizados, self.anexos = [], [], []
        self.falhar_com = None
        self.falhar_anexo = False

    def criar(self, dados, chave_operacao=None):
        if self.falhar_com:
            raise self.falhar_com
        self.criados.append((dados, chave_operacao))
        return {"id": "novo-1", **dados}

    def atualizar(self, documento_id, dados):
        if self.falhar_com:
            raise self.falhar_com
        self.atualizados.append((documento_id, dados))
        return {"id": documento_id, **dados}

    def anexar_comprovante(self, documento_id, moto_id, nome, conteudo, content_type):
        if self.falhar_anexo:
            raise RuntimeError("upload falhou")
        self.anexos.append((documento_id, moto_id, nome, conteudo, content_type))


@pytest.fixture
def servico_doc(monkeypatch, base_documentos):
    from src.web import acoes_documentos

    falso = ServicoFalso(base_documentos)
    monkeypatch.setattr(acoes_documentos, "documentos", SimpleNamespace(
        criar=falso.criar, atualizar=falso.atualizar, anexar_comprovante=falso.anexar_comprovante))
    return falso


def _dados(token, **extra):
    return {"csrf_token": token, "chave_operacao": "chave-1", "moto_id": "m2", "tipo": "seguro", "ano_referencia": "2026",
            "vencimento": "2026-12-31", "valor": "1.234,56", "descricao": "apólice 22", "observacoes": "", **extra}


def test_novo_traz_valores_iniciais_so_motos_ativas_e_campo_de_comprovante(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos/novo", headers=HX).text
    assert "<html" not in html and 'enctype="multipart/form-data"' in html and 'hx-encoding="multipart/form-data"' in html
    assert 'value="0,00"' in html and 'value="' + str(base_documentos.hoje.year) + '"' in html
    assert "BRA-2E19 · Honda CG 160" in html and "QRS-4T21" in html and "ZZZ-9Z99" not in html  # moto inativa não aceita documento
    assert '<option value="ipva" selected>' in html and 'name="comprovante" type="file"' in html
    assert 'name="chave_operacao" value="' in html
    pagina = cliente.get("/documentos/novo").text
    assert "<html" in pagina and 'id="form-documento"' in pagina and 'enctype="multipart/form-data"' in pagina


def test_novo_aceita_a_sugestao_do_ano_seguinte(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos/novo?moto=m2&tipo=seguro&ano=2027", headers=HX).text
    assert '<option value="m2" selected>' in html and '<option value="seguro" selected>' in html and 'value="2027"' in html
    assert 'name="vencimento" type="date" value=""' in html
    ignorado = cliente.get("/documentos/novo?moto=x&tipo=y&ano=z", headers=HX).text
    assert '<option value="ipva" selected>' in ignorado and 'value="' + str(base_documentos.hoje.year) + '"' in ignorado


def test_editar_trava_a_moto_e_avisa_do_comprovante_existente(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get(f"/documentos/{E1}/editar", headers=HX).text
    assert "Editar documento" in html and "BRA-2E19" in html and 'name="moto_id"' not in html
    assert "IPVA &lt;b&gt;2026&lt;/b&gt;" in html and "Já existe um comprovante anexado" in html
    assert "Já existe um comprovante" not in cliente.get(f"/documentos/{E2}/editar", headers=HX).text
    assert cliente.get("/documentos/00000000-0000-0000-0000-0000000000ff/editar").status_code == 404
    assert cliente.get("/documentos/abc/editar").status_code == 404


def test_cria_com_comprovante_e_volta_para_a_lista(cliente, base_documentos, servico_doc):
    entrar(cliente)
    resposta = cliente.post("/documentos/novo", data=_dados(csrf_da_sessao(cliente)), headers=HX,
                            files={"comprovante": ("recibo.pdf", PDF, "text/plain")})
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == "/documentos"
    dados, chave = servico_doc.criados[0]
    assert chave == "chave-1" and dados["moto_id"] == "m2" and dados["tipo"] == "seguro" and dados["ano_referencia"] == 2026
    assert dados["vencimento"] == "2026-12-31" and dados["valor"] == "1234.56" and dados["descricao"] == "apólice 22"
    assert dados["observacoes"] is None
    # O tipo de conteúdo vem da extensão, não do que o navegador declarou.
    assert servico_doc.anexos == [("novo-1", "m2", "recibo.pdf", PDF, "application/pdf")]
    assert "Documento Seguro 2026 da moto QRS-4T21 cadastrado." in cliente.get("/documentos").text


def test_cria_sem_javascript_e_sem_comprovante(cliente, base_documentos, servico_doc):
    entrar(cliente)
    resposta = cliente.post("/documentos/novo", data=_dados(csrf_da_sessao(cliente)), follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/documentos"
    assert len(servico_doc.criados) == 1 and servico_doc.anexos == []


def test_edita_mantendo_a_moto_do_documento(cliente, base_documentos, servico_doc):
    entrar(cliente)
    resposta = cliente.post(f"/documentos/{E2}/editar", data=_dados(csrf_da_sessao(cliente), moto_id="m2", valor="99,90"), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == "/documentos"
    documento_id, dados = servico_doc.atualizados[0]
    assert documento_id == E2 and dados["moto_id"] == "m1" and dados["valor"] == "99.90" and servico_doc.criados == []
    assert "Documento Seguro 2026 da moto BRA-2E19 atualizado." in cliente.get("/documentos").text


def test_comprovante_que_falha_nao_desfaz_o_documento(cliente, base_documentos, servico_doc):
    entrar(cliente)
    servico_doc.falhar_anexo = True
    resposta = cliente.post("/documentos/novo", data=_dados(csrf_da_sessao(cliente)), headers=HX,
                            files={"comprovante": ("recibo.pdf", PDF, "application/pdf")})
    assert resposta.status_code == 200 and len(servico_doc.criados) == 1
    assert "o comprovante não foi enviado" in cliente.get("/documentos").text


def test_erros_por_campo_nao_gravam_nada_e_preservam_o_digitado(cliente, base_documentos, servico_doc):
    entrar(cliente)
    resposta = cliente.post("/documentos/novo", headers=HX, data=_dados(csrf_da_sessao(cliente), vencimento="", valor="abc", ano_referencia="1800"),
                            files={"comprovante": ("virus.exe", b"MZ", "application/octet-stream")})
    html = resposta.text
    assert resposta.status_code == 422 and servico_doc.criados == [] and servico_doc.anexos == []
    assert "Corrija os campos destacados." in html and 'aria-invalid="true"' in html
    assert "Vencimento: informe uma data." in html and "Valor:" in html and "o menor valor aceito é 1900" in html
    assert "Extensão não permitida" in html and "escolha-o de novo" in html
    assert 'value="abc"' in html and "apólice 22" in html and 'name="chave_operacao" value="chave-1"' in html


def test_comprovante_de_conteudo_falso_e_recusado(cliente, base_documentos, servico_doc):
    entrar(cliente)
    resposta = cliente.post("/documentos/novo", headers=HX, data=_dados(csrf_da_sessao(cliente)),
                            files={"comprovante": ("recibo.pdf", b"isto nao e um pdf", "application/pdf")})
    assert resposta.status_code == 422 and "não corresponde à extensão" in resposta.text and servico_doc.criados == []


def test_erro_do_servico_aparece_no_formulario(cliente, base_documentos, servico_doc):
    entrar(cliente)
    servico_doc.falhar_com = ValueError("Documento duplicado.")
    resposta = cliente.post("/documentos/novo", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 422 and "Documento duplicado." in resposta.text


def test_moto_invalida_e_documento_inexistente(cliente, base_documentos, servico_doc):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    invalida = cliente.post("/documentos/novo", data=_dados(token, moto_id="m3"), headers=HX)  # moto inativa
    assert invalida.status_code == 422 and "escolha uma moto da frota" in invalida.text and servico_doc.criados == []
    assert cliente.post("/documentos/abc/editar", data=_dados(token), headers=HX).status_code == 404


def test_formularios_exigem_csrf_e_dono(cliente, base_documentos, servico_doc):
    assert cliente.get("/documentos/novo").status_code == 303
    entrar(cliente)
    assert cliente.post("/documentos/novo", data=_dados("errado")).status_code == 403 and servico_doc.criados == []
    cliente.cookies.clear()
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/documentos/novo").status_code == 403
    assert cliente.post(f"/documentos/{E1}/editar", data=_dados("x")).status_code == 403


def test_lista_oferece_novo_e_editar(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos").text
    assert 'hx-get="/documentos/novo"' in html and f'hx-get="/documentos/{E1}/editar"' in html
    # Os botões ficam dentro do formulário de filtros (hx-push-url="true"): sem o "false" o diálogo trocaria o endereço da página.
    assert html.count('hx-target="#dlg-form-conteudo" hx-swap="innerHTML" hx-push-url="false"') == html.count('>Editar<') + html.count('>Regularizar<')
    base_documentos.documentos.clear()
    assert 'href="/documentos/novo"' in cliente.get("/documentos").text
