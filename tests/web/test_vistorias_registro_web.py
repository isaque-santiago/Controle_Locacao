"""Fase 3: Vistorias parte B (registrar vistoria com fotos, em diálogo e em página)."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.domain.valores import hoje_br
from src.domain.vistorias import CHECKLIST_PADRAO
from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}
SEM_VISTORIAS = "00000000-0000-0000-0000-0000000000d3"
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class ServicoFalso:
    def __init__(self):
        self.registros, self.fotos = [], []
        self.falhar_com = None
        self.fotos_que_falham = set()

    def registrar_vistoria(self, contrato_id, moto_id, tipo, **dados):
        if self.falhar_com:
            raise self.falhar_com
        self.registros.append((contrato_id, moto_id, tipo, dados))
        return {"vistoria_id": "nova-1"}

    def anexar_foto(self, vistoria_id, nome, conteudo, content_type, legenda=None):
        if nome in self.fotos_que_falham:
            raise RuntimeError("upload falhou")
        self.fotos.append((vistoria_id, nome, conteudo, content_type))


@pytest.fixture
def servico_vist(monkeypatch):
    from src.web import acoes_vistorias

    falso = ServicoFalso()
    monkeypatch.setattr(acoes_vistorias, "vistorias", SimpleNamespace(
        registrar_vistoria=falso.registrar_vistoria, anexar_foto=falso.anexar_foto))
    return falso


def _dados(token, **extra):
    return {"csrf_token": token, "contrato": SEM_VISTORIAS, "tipo": "entrega", "data": hoje_br().isoformat(),
            "km": "12.050", "nivel_combustivel": "1/2", "avarias": " Risco no tanque ", "adicionais": "capa de chuva=ok",
            **{"item_" + i: "ok" for i in CHECKLIST_PADRAO}, "item_buzina": "avaria", **extra}


def _fotos(*itens):
    return [("fotos", item) for item in itens]


def test_etapa_um_lista_contratos_pendentes_com_ativos_primeiro(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get("/vistorias/registrar").text
    assert "Maria &lt;b&gt;Silva&lt;/b&gt; → BRA-2E19" in html and "(ativo)" in html and "(encerrado)" in html
    assert html.index(SEM_VISTORIAS) < html.index("0000000000d2")
    assert "0000000000d1" not in html  # já tem as duas vistorias
    trecho = cliente.get("/vistorias/registrar", headers=HX).text
    assert "<html" not in trecho and 'id="form-dialogo"' in trecho and 'method="get"' in trecho and "Continuar" in trecho


def test_etapa_um_sem_pendentes_diz_que_esta_tudo_registrado(cliente, base_vistorias):
    entrar(cliente)
    base_vistorias.contratos[:] = base_vistorias.contratos[:1]
    html = cliente.get("/vistorias/registrar").text
    assert "Todos os contratos já têm vistoria" in html and "Continuar" not in html


def test_etapa_dois_traz_valores_iniciais_e_campo_de_fotos(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get(f"/vistorias/registrar?contrato={SEM_VISTORIAS}", headers=HX).text
    assert "<html" not in html and 'enctype="multipart/form-data"' in html and 'hx-encoding="multipart/form-data"' in html
    assert 'name="contrato" value="' + SEM_VISTORIAS in html and 'value="12000"' in html
    assert 'value="' + hoje_br().isoformat() + '"' in html and 'min="2026-09-01"' in html
    assert '<option value="entrega" selected>' in html and '<option value="devolucao"' in html
    assert '<option value="cheio" selected>' in html and 'name="fotos" type="file" multiple' in html
    assert "Alterar contrato" in html and 'hx-get="/vistorias/registrar"' in html
    pagina = cliente.get(f"/vistorias/registrar?contrato={SEM_VISTORIAS}").text
    assert "<html" in pagina and 'id="form-registro"' in pagina and 'enctype="multipart/form-data"' in pagina


def test_etapa_dois_oferece_so_o_tipo_que_falta(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get("/vistorias/registrar?contrato=00000000-0000-0000-0000-0000000000d2", headers=HX).text
    assert '<option value="devolucao" selected>' in html and 'value="entrega"' not in html


def test_contrato_completo_volta_para_a_comparacao_e_inexistente_da_404(cliente, base_vistorias):
    entrar(cliente)
    resposta = cliente.get("/vistorias/registrar?contrato=" + base_vistorias.contratos[0]["id"], follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"].endswith(base_vistorias.contratos[0]["id"])
    assert "já tem as vistorias" in cliente.get(resposta.headers["location"]).text
    assert cliente.get("/vistorias/registrar?contrato=00000000-0000-0000-0000-0000000000ff").status_code == 404
    assert cliente.get("/vistorias/registrar?contrato=abc").status_code == 404


def test_registra_com_fotos_e_volta_para_a_comparacao(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/vistorias/registrar", data=_dados(token), headers=HX,
                            files=_fotos(("a.jpg", JPG, "image/gif"), ("b.png", PNG, "image/png")))
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == f"/vistorias/contrato/{SEM_VISTORIAS}"
    contrato, moto, tipo, dados = servico_vist.registros[0]
    assert (contrato, moto, tipo) == (SEM_VISTORIAS, "m1", "entrega")
    assert dados["km"] == 12050 and dados["nivel_combustivel"] == "1/2" and dados["avarias"] == "Risco no tanque"
    assert dados["checklist"]["buzina"] == "avaria" and dados["checklist"]["capa de chuva"] == "ok"
    assert dados["data"].date() == hoje_br()
    # O tipo de conteúdo vem da extensão, não do que o navegador declarou.
    assert [(f[0], f[1], f[3]) for f in servico_vist.fotos] == [("nova-1", "a.jpg", "image/jpeg"), ("nova-1", "b.png", "image/png")]
    assert "Vistoria de entrega da moto BRA-2E19 registrada." in cliente.get(resposta.headers["HX-Redirect"]).text


def test_registra_sem_javascript_e_sem_fotos(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    resposta = cliente.post("/vistorias/registrar", data=_dados(csrf_da_sessao(cliente), tipo="devolucao"),
                            follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/vistorias/contrato/{SEM_VISTORIAS}"
    assert servico_vist.registros[0][2] == "devolucao" and servico_vist.fotos == []


def test_foto_que_falha_nao_desfaz_a_vistoria_e_o_aviso_conta_as_falhas(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    servico_vist.fotos_que_falham = {"a.jpg"}
    resposta = cliente.post("/vistorias/registrar", data=_dados(csrf_da_sessao(cliente)), headers=HX,
                            files=_fotos(("a.jpg", JPG, "image/jpeg"), ("b.jpg", JPG, "image/jpeg")))
    assert resposta.status_code == 200 and len(servico_vist.registros) == 1 and len(servico_vist.fotos) == 1
    assert "1 foto não foi enviada" in cliente.get(resposta.headers["HX-Redirect"]).text


def test_erros_por_campo_nao_gravam_nada_e_pedem_as_fotos_de_novo(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    amanha = (hoje_br() + timedelta(days=1)).isoformat()
    resposta = cliente.post("/vistorias/registrar", data=_dados(csrf_da_sessao(cliente), km="11999", data=amanha),
                            headers=HX, files=_fotos(("a.gif", b"GIF89a", "image/gif")))
    html = resposta.text
    assert resposta.status_code == 422 and servico_vist.registros == [] and servico_vist.fotos == []
    assert "Corrija os campos destacados." in html and 'aria-invalid="true"' in html
    assert "data futura" in html and "Extensão não permitida" in html and "a.gif" in html
    assert "escolha as fotos de novo" in html
    assert 'value="11999"' in html and "Risco no tanque" in html  # o que foi digitado continua no formulário


def test_mais_de_dez_fotos_e_recusado_antes_de_gravar(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    resposta = cliente.post("/vistorias/registrar", data=_dados(csrf_da_sessao(cliente)), headers=HX,
                            files=_fotos(*[(f"{n}.jpg", JPG, "image/jpeg") for n in range(11)]))
    assert resposta.status_code == 422 and "até 10 fotos" in resposta.text and servico_vist.registros == []


def test_vistoria_duplicada_mostra_o_erro_do_servico(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    servico_vist.falhar_com = ValueError("Já existe uma vistoria de 'entrega' para este contrato.")
    resposta = cliente.post("/vistorias/registrar", data=_dados(csrf_da_sessao(cliente)), headers=HX)
    assert resposta.status_code == 422 and "Já existe uma vistoria de" in resposta.text and servico_vist.fotos == []


def test_tipo_ja_registrado_e_contrato_inexistente(cliente, base_vistorias, servico_vist):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/vistorias/registrar", data=_dados(token, contrato="00000000-0000-0000-0000-0000000000d2"), headers=HX)
    assert resposta.status_code == 422 and "ainda não registrado" in resposta.text
    assert cliente.post("/vistorias/registrar", data=_dados(token, contrato="abc"), headers=HX).status_code == 404


def test_registro_exige_csrf_e_dono(cliente, base_vistorias, servico_vist):
    assert cliente.get("/vistorias/registrar").status_code == 303
    entrar(cliente)
    assert cliente.post("/vistorias/registrar", data=_dados("errado")).status_code == 403
    assert servico_vist.registros == []
    cliente.cookies.clear()
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/vistorias/registrar").status_code == 403
    assert cliente.post("/vistorias/registrar", data=_dados("x")).status_code == 403


def test_lista_e_comparacao_oferecem_o_registro(cliente, base_vistorias):
    entrar(cliente)
    assert 'hx-get="/vistorias/registrar"' in cliente.get("/vistorias").text
    base_vistorias.registradas.remove(base_vistorias.devolucao)
    comparacao = cliente.get(f"/vistorias/contrato/{base_vistorias.contratos[0]['id']}").text
    assert f"/vistorias/registrar?contrato={base_vistorias.contratos[0]['id']}" in comparacao
    assert "Registrar vistoria de devolução" in comparacao
