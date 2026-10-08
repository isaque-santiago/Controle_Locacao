"""Fase 3: Documentos parte C (regularizar, com comprovante e cadastro do ano seguinte)."""

from datetime import date
from types import SimpleNamespace

import pytest

from src.domain.documentos import sugerir_proximo_documento
from src.domain.valores import hoje_br
from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}
E1 = "00000000-0000-0000-0000-0000000000e1"  # IPVA vencido, com comprovante, moto m1
E2 = "00000000-0000-0000-0000-0000000000e2"  # seguro a vencer, moto m1
E4 = "00000000-0000-0000-0000-0000000000e4"  # já regularizado
E5 = "00000000-0000-0000-0000-0000000000e5"  # "outro": sem renovação anual
PDF = b"%PDF-1.7" + b"0" * 64


class ServicoFalso:
    def __init__(self):
        self.regularizados, self.anexos = [], []
        self.falhar_anexo = False
        self.falhar_regularizar = None
        self.tipo_por_id = {E1: "ipva", E2: "seguro", E5: "outro"}

    def regularizar(self, documento_id, data):
        if self.falhar_regularizar:
            raise self.falhar_regularizar
        self.regularizados.append((documento_id, data))
        tipo = self.tipo_por_id[documento_id]
        return {"documento": {"id": documento_id}, "sugestao_proximo": sugerir_proximo_documento(tipo, 2026)}

    def anexar_comprovante(self, documento_id, moto_id, nome, conteudo, content_type):
        if self.falhar_anexo:
            raise RuntimeError("upload falhou")
        self.anexos.append((documento_id, moto_id, nome, content_type))


@pytest.fixture
def servico_reg(monkeypatch, base_documentos):
    from src.web import acoes_documentos

    falso = ServicoFalso()
    monkeypatch.setattr(acoes_documentos, "documentos", SimpleNamespace(
        regularizar=falso.regularizar, anexar_comprovante=falso.anexar_comprovante))
    return falso


def _dados(token, **extra):
    return {"csrf_token": token, "data": "2026-10-08", **extra}


def test_formulario_traz_data_de_hoje_e_oferece_o_ano_seguinte(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get(f"/documentos/{E2}/regularizar", headers=HX).text
    assert "<html" not in html and 'enctype="multipart/form-data"' in html and "Marcar como regularizado" in html
    assert f'value="{hoje_br().isoformat()}"' in html and "BRA-2E19" in html and "Seguro 2026" in html
    assert "Cadastrar em seguida o documento de 2027" in html and 'name="criar_proximo" checked' in html
    assert 'name="comprovante" type="file"' in html
    assert "Cadastrar em seguida" not in cliente.get(f"/documentos/{E5}/regularizar", headers=HX).text  # sem renovação anual
    assert "Já existe um comprovante anexado" in cliente.get(f"/documentos/{E1}/regularizar", headers=HX).text
    assert 'id="form-regularizar"' in cliente.get(f"/documentos/{E2}/regularizar").text


def test_documento_ja_regularizado_volta_para_a_lista_e_inexistente_da_404(cliente, base_documentos):
    entrar(cliente)
    resposta = cliente.get(f"/documentos/{E4}/regularizar", follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/documentos"
    assert "já está regularizado" in cliente.get("/documentos").text
    assert cliente.get("/documentos/00000000-0000-0000-0000-0000000000ff/regularizar").status_code == 404
    assert cliente.get("/documentos/abc/regularizar").status_code == 404


def test_regulariza_e_abre_o_cadastro_do_ano_seguinte(cliente, base_documentos, servico_reg):
    entrar(cliente)
    resposta = cliente.post(f"/documentos/{E2}/regularizar", data=_dados(csrf_da_sessao(cliente), criar_proximo="on"), headers=HX,
                            files={"comprovante": ("recibo.pdf", PDF, "text/plain")})
    assert resposta.status_code == 200
    assert resposta.headers["HX-Redirect"] == "/documentos/novo?moto=m1&tipo=seguro&ano=2027"
    assert servico_reg.regularizados == [(E2, date(2026, 10, 8))]
    assert servico_reg.anexos == [(E2, "m1", "recibo.pdf", "application/pdf")]
    pagina = cliente.get(resposta.headers["HX-Redirect"]).text
    assert "marcado como regularizado" in pagina and "Seguro 2026 da moto BRA-2E19" in pagina and "O cadastro do próximo já está aberto" in pagina
    assert '<option value="seguro" selected>' in pagina and 'value="2027"' in pagina


def test_regulariza_sem_pedir_o_proximo_ou_sem_sugestao_volta_para_a_lista(cliente, base_documentos, servico_reg):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    sem_marcar = cliente.post(f"/documentos/{E2}/regularizar", data=_dados(token), follow_redirects=False)
    assert sem_marcar.status_code == 303 and sem_marcar.headers["location"] == "/documentos"
    outro = cliente.post(f"/documentos/{E5}/regularizar", data=_dados(token, criar_proximo="on"), headers=HX)
    assert outro.headers["HX-Redirect"] == "/documentos" and len(servico_reg.regularizados) == 2 and servico_reg.anexos == []
    assert "Documento Outro 2026 da moto QRS-4T21 marcado como regularizado." in cliente.get("/documentos").text


def test_comprovante_invalido_nao_regulariza_nada(cliente, base_documentos, servico_reg):
    entrar(cliente)
    resposta = cliente.post(f"/documentos/{E2}/regularizar", data=_dados(csrf_da_sessao(cliente), data=""), headers=HX,
                            files={"comprovante": ("virus.exe", b"MZ", "application/octet-stream")})
    html = resposta.text
    assert resposta.status_code == 422 and servico_reg.regularizados == [] and servico_reg.anexos == []
    assert "Data de regularização: informe uma data." in html and "Extensão não permitida" in html and "escolha-o de novo" in html


def test_falha_no_envio_do_comprovante_mantem_o_documento_pendente(cliente, base_documentos, servico_reg):
    entrar(cliente)
    servico_reg.falhar_anexo = True
    resposta = cliente.post(f"/documentos/{E2}/regularizar", data=_dados(csrf_da_sessao(cliente)), headers=HX,
                            files={"comprovante": ("recibo.pdf", PDF, "application/pdf")})
    assert resposta.status_code in (500, 503) and servico_reg.regularizados == []


def test_documento_ja_regularizado_nao_regulariza_de_novo(cliente, base_documentos, servico_reg):
    entrar(cliente)
    resposta = cliente.post(f"/documentos/{E4}/regularizar", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 422 and "já foi regularizado" in resposta.text and servico_reg.regularizados == []


def test_regularizacao_exige_csrf_e_dono(cliente, base_documentos, servico_reg):
    assert cliente.get(f"/documentos/{E2}/regularizar").status_code == 303
    entrar(cliente)
    assert cliente.post(f"/documentos/{E2}/regularizar", data=_dados("errado")).status_code == 403
    assert servico_reg.regularizados == []
    cliente.cookies.clear()
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(f"/documentos/{E2}/regularizar").status_code == 403
    assert cliente.post(f"/documentos/{E2}/regularizar", data=_dados("x")).status_code == 403


def test_lista_oferece_regularizar_so_para_pendentes(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos").text
    assert f'hx-get="/documentos/{E2}/regularizar"' in html and f'hx-get="/documentos/{E4}/regularizar"' not in html
