"""Adicionar fotos a uma vistoria já registrada (diálogo e página), a partir da comparação entrega × devolução."""

from types import SimpleNamespace

import pytest

from tests.web.conftest import CONTRATO_VISTORIAS, VISTORIA_DEVOLUCAO, VISTORIA_ENTREGA, csrf_da_sessao, entrar

HX = {"HX-Request": "true"}
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
INEXISTENTE = "00000000-0000-0000-0000-0000000000aa"


@pytest.fixture
def storage(monkeypatch):
    """Serviço de vistorias falso: guarda o que seria enviado e deixa escolher quais fotos falham."""
    from src.web import acoes_vistorias

    class Falso:
        def __init__(self):
            self.fotos, self.que_falham = [], set()

        def anexar_foto(self, vistoria_id, nome, conteudo, content_type, legenda=None):
            if nome in self.que_falham:
                raise RuntimeError("upload falhou")
            self.fotos.append((vistoria_id, nome, content_type))

    falso = Falso()
    monkeypatch.setattr(acoes_vistorias, "vistorias", SimpleNamespace(anexar_foto=falso.anexar_foto))
    return falso


def _enviar(cliente, vistoria_id, *arquivos, **extra):
    return cliente.post(f"/vistorias/{vistoria_id}/fotos", data={"csrf_token": csrf_da_sessao(cliente)},
                        files=[("fotos", a) for a in arquivos], **extra)


def test_comparacao_oferece_adicionar_fotos_so_onde_ha_vistoria(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get(f"/vistorias/contrato/{CONTRATO_VISTORIAS}").text
    assert html.count("Adicionar fotos") == 2
    assert f'hx-get="/vistorias/{VISTORIA_ENTREGA}/fotos"' in html and f'hx-get="/vistorias/{VISTORIA_DEVOLUCAO}/fotos"' in html
    sem_devolucao = cliente.get("/vistorias/contrato/00000000-0000-0000-0000-0000000000d2").text
    assert sem_devolucao.count("Adicionar fotos") == 1 and "Ainda não realizada" in sem_devolucao


def test_dialogo_conta_as_fotos_atuais_e_aceita_imagem_de_camera(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get(f"/vistorias/{VISTORIA_ENTREGA}/fotos", headers=HX).text
    assert "<html" not in html and 'id="form-dialogo"' in html and 'hx-encoding="multipart/form-data"' in html
    assert 'name="fotos" type="file" multiple accept="image/*"' in html and "Já tem 2 foto(s)" in html
    # Campo múltiplo só abre a galeria no Android: o segundo campo `fotos` abre a câmera.
    assert 'name="fotos" type="file" accept="image/*" capture="environment"' in html and "Tirar foto agora" in html
    assert "Entrega" in html and "BRA-2E19" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html
    assert "Ainda não tem fotos" in cliente.get(f"/vistorias/{VISTORIA_DEVOLUCAO}/fotos", headers=HX).text
    pagina = cliente.get(f"/vistorias/{VISTORIA_DEVOLUCAO}/fotos").text
    assert "<html" in pagina and 'id="form-fotos"' in pagina and 'enctype="multipart/form-data"' in pagina
    assert f'href="/vistorias/contrato/{CONTRATO_VISTORIAS}"' in pagina


def test_anexa_as_fotos_e_volta_para_a_comparacao(cliente, base_vistorias, storage):
    entrar(cliente)
    resposta = _enviar(cliente, VISTORIA_DEVOLUCAO, ("a.jpg", JPG, "image/gif"), ("b.png", PNG, "image/png"), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == f"/vistorias/contrato/{CONTRATO_VISTORIAS}"
    # O tipo de conteúdo vem da extensão, não do que o navegador declarou.
    assert storage.fotos == [(VISTORIA_DEVOLUCAO, "a.jpg", "image/jpeg"), (VISTORIA_DEVOLUCAO, "b.png", "image/png")]
    assert "2 fotos anexadas." in cliente.get(resposta.headers["HX-Redirect"]).text


def test_sem_javascript_redireciona(cliente, base_vistorias, storage):
    entrar(cliente)
    resposta = _enviar(cliente, VISTORIA_ENTREGA, ("a.jpg", JPG, "image/jpeg"), follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/vistorias/contrato/{CONTRATO_VISTORIAS}"
    assert "1 foto anexada." in cliente.get(resposta.headers["location"]).text


def test_foto_que_falha_nao_impede_as_outras_e_o_aviso_conta(cliente, base_vistorias, storage):
    entrar(cliente)
    storage.que_falham = {"a.jpg"}
    resposta = _enviar(cliente, VISTORIA_ENTREGA, ("a.jpg", JPG, "image/jpeg"), ("b.jpg", JPG, "image/jpeg"), headers=HX)
    assert resposta.status_code == 200 and storage.fotos == [(VISTORIA_ENTREGA, "b.jpg", "image/jpeg")]
    aviso = cliente.get(resposta.headers["HX-Redirect"]).text
    assert "1 foto anexada." in aviso and "1 foto não foi enviada" in aviso and "Adicionar fotos" in aviso


def test_sem_foto_ou_com_arquivo_invalido_nao_envia_nada(cliente, base_vistorias, storage):
    entrar(cliente)
    sem = cliente.post(f"/vistorias/{VISTORIA_ENTREGA}/fotos", data={"csrf_token": csrf_da_sessao(cliente)}, headers=HX)
    assert sem.status_code == 422 and "escolha ao menos uma foto" in sem.text and 'id="form-dialogo"' in sem.text
    gif = _enviar(cliente, VISTORIA_ENTREGA, ("a.jpg", JPG, "image/jpeg"), ("b.gif", b"GIF89a", "image/gif"), headers=HX)
    assert gif.status_code == 422 and "b.gif" in gif.text and storage.fotos == []
    muitas = _enviar(cliente, VISTORIA_ENTREGA, *[(f"{i}.jpg", JPG, "image/jpeg") for i in range(11)], headers=HX)
    assert muitas.status_code == 422 and "até 10 fotos" in muitas.text and storage.fotos == []


def test_vistoria_inexistente_ou_id_invalido_da_404(cliente, base_vistorias, storage):
    entrar(cliente)
    for destino in (INEXISTENTE, "abc"):
        assert cliente.get(f"/vistorias/{destino}/fotos").status_code == 404
        assert _enviar(cliente, destino, ("a.jpg", JPG, "image/jpeg")).status_code == 404
    assert storage.fotos == []
