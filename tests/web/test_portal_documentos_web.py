"""Portal do locatário: documentos da moto e envio do comprovante (aguarda o dono; não regulariza nada)."""

from tests.web.conftest import (
    DOC_PORTAL_AGUARDANDO, DOC_PORTAL_RECUSADO, DOC_PORTAL_VENCIDO, csrf_da_sessao, entrar, extrair_csrf,
)

PDF = b"%PDF-1.7 comprovante de teste"
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
CLIENTE_PORTAL = "00000000-0000-0000-0000-0000000000c9"


def _locatario(cliente):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")


def _token(cliente):
    return extrair_csrf(cliente.get("/portal").text)


def _enviar(cliente, documento=DOC_PORTAL_VENCIDO, arquivo=("comprovante.pdf", PDF, "application/pdf"), token=None, **extra):
    arquivos = {"comprovante": arquivo} if arquivo else {}
    return cliente.post(f"/portal/documentos/{documento}/comprovante", data={"csrf_token": token or _token(cliente), **extra},
                        files=arquivos or None, follow_redirects=False)


def test_portal_lista_os_documentos_com_situacao_e_o_que_fazer(cliente, base_portal):
    _locatario(cliente)
    html = cliente.get("/portal").text
    assert "Documentos da moto" in html and "Troca de óleo e documentos da sua moto." in html
    assert "IPVA 2026" in html and "Seguro 2026" in html and "Licenciamento 2026" in html and "BRA-2E19" in html
    assert "Vencido" in html and "A vencer" in html and "05/10/2026" in html
    # o vencido e o recusado têm formulário; o aguardando mostra o aviso e não tem
    assert f'action="/portal/documentos/{DOC_PORTAL_VENCIDO}/comprovante"' in html
    assert f'action="/portal/documentos/{DOC_PORTAL_RECUSADO}/comprovante"' in html
    assert f'action="/portal/documentos/{DOC_PORTAL_AGUARDANDO}/comprovante"' not in html
    assert "Recebemos o seu comprovante" in html and "Aguardando conferência" in html and "enviado em 10/11/2026 12:30" in html
    assert "O proprietário recusou o comprovante: Foto cortada" in html and "Recusado" in html
    assert 'name="comprovante" type="file"' in html and 'accept="application/pdf,image/*"' in html and 'name="observacao"' in html
    assert "Também pode enviar o comprovante por WhatsApp" in html


def test_sem_documentos_pendentes_a_secao_nao_aparece(cliente, base_portal):
    base_portal.documentos.clear()
    _locatario(cliente)
    html = cliente.get("/portal").text
    assert "Documentos da moto" not in html and "Olá, Ana" in html


def test_falha_ao_ler_os_documentos_nao_derruba_o_portal(cliente, base_portal):
    base_portal.erro_nos_documentos = RuntimeError("função inexistente")
    _locatario(cliente)
    resposta = cliente.get("/portal")
    assert resposta.status_code == 200
    assert "Não foi possível carregar os documentos agora" in resposta.text and "Reportar troca de óleo" in resposta.text


def test_envia_o_pdf_e_volta_para_os_documentos_com_aviso(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, observacao="  Paguei a guia à vista  ")
    assert r.status_code == 303 and r.headers["location"] == "/portal#documentos"
    assert base_portal.comprovantes_enviados == [(CLIENTE_PORTAL, DOC_PORTAL_VENCIDO, "comprovante.pdf", PDF, "Paguei a guia à vista")]
    assert "Comprovante de IPVA 2026 enviado" in cliente.get("/portal").text


def test_envia_foto_sem_observacao(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, documento=DOC_PORTAL_RECUSADO, arquivo=("foto.jpg", JPG, "image/jpeg"))
    assert r.status_code == 303
    assert base_portal.comprovantes_enviados == [(CLIENTE_PORTAL, DOC_PORTAL_RECUSADO, "foto.jpg", JPG, None)]


def test_sem_arquivo_mostra_o_erro_ao_lado_do_campo_e_nao_envia(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, arquivo=None, observacao="Paguei")
    assert r.status_code == 422 and base_portal.comprovantes_enviados == []
    assert "Comprovante: anexe a foto ou o PDF do comprovante." in r.text and 'aria-invalid="true"' in r.text
    assert "Corrija os campos destacados." in r.text and 'value="Paguei"' in r.text  # o que foi digitado volta


def test_arquivo_de_tipo_errado_ou_falso_e_recusado(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, arquivo=("virus.exe", b"MZ" + b"0" * 40, "application/octet-stream"))
    assert r.status_code == 422 and "Extensão não permitida" in r.text
    r = _enviar(cliente, arquivo=("falso.pdf", b"isso nao e pdf", "application/pdf"))
    assert r.status_code == 422 and "não corresponde à extensão" in r.text
    assert base_portal.comprovantes_enviados == []


def test_arquivo_grande_demais_e_recusado(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, arquivo=("grande.pdf", b"%PDF-" + b"0" * (11 * 1024 * 1024), "application/pdf"))
    assert r.status_code in (413, 422) and base_portal.comprovantes_enviados == []


def test_observacao_longa_e_recusada_e_volta_digitada(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, observacao="x" * 201)
    assert r.status_code == 422 and "Observação: use no máximo 200 caracteres." in r.text and base_portal.comprovantes_enviados == []


def test_documento_que_ja_aguarda_conferencia_nao_aceita_outro_envio(cliente, base_portal):
    _locatario(cliente)
    r = _enviar(cliente, documento=DOC_PORTAL_AGUARDANDO)
    assert r.status_code == 422 and "aguardando conferência do proprietário" in r.text and base_portal.comprovantes_enviados == []


def test_documento_de_outro_locatario_ou_id_invalido_e_404(cliente, base_portal):
    _locatario(cliente)
    token = _token(cliente)
    assert _enviar(cliente, documento="00000000-0000-0000-0000-00000000ffff", token=token).status_code == 404
    assert _enviar(cliente, documento="nao-e-uuid", token=token).status_code == 404
    assert base_portal.comprovantes_enviados == []


def test_regra_do_servico_aparece_no_formulario(cliente, base_portal):
    base_portal.falhar_com = ValueError("Este documento já está regularizado.")
    _locatario(cliente)
    r = _enviar(cliente)
    assert r.status_code == 422 and "Este documento já está regularizado." in r.text


def test_exige_csrf_login_e_papel_de_locatario(cliente, base_portal):
    assert _enviar(cliente, token="x").status_code in (302, 303, 400, 403)  # sem login
    entrar(cliente)  # dono
    token = csrf_da_sessao(cliente)
    r = cliente.post(f"/portal/documentos/{DOC_PORTAL_VENCIDO}/comprovante", data={"csrf_token": token},
                     files={"comprovante": ("c.pdf", PDF, "application/pdf")}, follow_redirects=False)
    assert r.status_code == 403
    cliente.cookies.clear()
    _locatario(cliente)
    r = cliente.post(f"/portal/documentos/{DOC_PORTAL_VENCIDO}/comprovante", data={"csrf_token": "errado"},
                     files={"comprovante": ("c.pdf", PDF, "application/pdf")}, follow_redirects=False)
    assert r.status_code in (400, 403)
    assert base_portal.comprovantes_enviados == []
