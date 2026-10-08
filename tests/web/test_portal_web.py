"""Fase 3: Portal do Locatário (contrato, troca de óleo com fotos e troca de senha)."""

from decimal import Decimal

from tests.web.conftest import CONTRATO_PORTAL, CONTRATO_PORTAL_SEM_PLANO, csrf_da_sessao, entrar, extrair_csrf

JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
SENHA_NOVA = "novaSenha2026"


def _locatario(cliente):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")


def _token(cliente):
    """O locatário não tem o Dashboard: o token vem da própria página do portal."""
    return extrair_csrf(cliente.get("/portal").text)


def _fotos(**extra):
    base = {"foto": ("painel.jpg", JPG, "text/plain"), "nota": ("nota.png", PNG, "image/png")}
    base.update(extra)
    return {k: v for k, v in base.items() if v is not None}


def _troca(cliente, contrato=CONTRATO_PORTAL, km="12.300", arquivos=None, token=None, **extra):
    return cliente.post(f"/portal/troca-oleo/{contrato}", data={"csrf_token": token or _token(cliente), "km": km, **extra},
                        files=_fotos() if arquivos is None else arquivos, follow_redirects=False)


def test_pagina_mostra_o_contrato_a_situacao_e_os_formularios(cliente, base_portal):
    _locatario(cliente)
    html = cliente.get("/portal").text
    assert "Olá, Ana" in html and "Souza" not in html.split("Olá, Ana")[1][:20]  # só o primeiro nome
    assert "BRA-2E19" in html and "CG &lt;i&gt;160&lt;/i&gt;" in html and "<i>160</i>" not in html
    assert "Óleo em dia" in html and "12.000 km" in html and "11.000 km" in html and "12.500 km" in html and "500 km" in html
    assert "multa fixa de" in html and "R$ 50,00" in html
    assert f'action="/portal/troca-oleo/{CONTRATO_PORTAL}"' in html and 'enctype="multipart/form-data"' in html
    assert 'name="km"' in html and 'name="foto" type="file"' in html and 'name="nota" type="file"' in html
    assert "Últimas trocas reportadas" in html and "01/09/2026" in html and "multa aplicada" in html
    assert 'action="/portal/senha"' in html and 'type="password"' in html and "Portal em migração" not in html


def test_moto_sem_plano_avisa_e_nao_mostra_o_formulario(cliente, base_portal):
    _locatario(cliente)
    html = cliente.get("/portal").text
    assert "QRS-4T21" in html and "ainda não foi configurado" in html
    assert f'action="/portal/troca-oleo/{CONTRATO_PORTAL_SEM_PLANO}"' not in html


def test_sem_contrato_ativo_mostra_estado_vazio_e_a_troca_de_senha(cliente, base_portal):
    _locatario(cliente)
    base_portal.dados["contratos"] = []
    html = cliente.get("/portal").text
    assert "Você não tem contrato ativo no momento" in html and 'action="/portal/senha"' in html


def test_situacao_proxima_e_vencida(cliente, base_portal):
    _locatario(cliente)
    base_portal.dados["contratos"][0]["km_atual"] = 12300  # faltam 200 km, dentro do alerta de 300
    assert "Troca de óleo próxima" in cliente.get("/portal").text
    base_portal.dados["contratos"][0]["km_atual"] = 12500
    assert "Troca de óleo vencida" in cliente.get("/portal").text


def test_dono_nao_usa_o_portal_e_sem_login_vai_para_a_entrada(cliente, base_portal):
    assert cliente.get("/portal").status_code == 303 and "/login" in cliente.get("/portal").headers["location"]
    entrar(cliente)
    assert cliente.get("/portal").headers["location"] == "/"
    token = csrf_da_sessao(cliente)
    assert _troca(cliente, token=token).status_code == 403
    assert cliente.post("/portal/senha", data={"csrf_token": token, "nova": SENHA_NOVA, "confirmacao": SENHA_NOVA}).status_code == 403
    assert base_portal.registros == []


def test_locatario_nao_entra_nas_telas_do_dono(cliente, base_portal):
    _locatario(cliente)
    for caminho in ("/motos", "/clientes", "/contratos", "/cobrancas", "/relatorios", "/configuracoes", "/documentos", "/vistorias"):
        assert cliente.get(caminho).status_code == 403, caminho
    assert cliente.post("/configuracoes/backup", data={"csrf_token": _token(cliente)}).status_code == 403


def test_envia_a_troca_com_as_duas_fotos_e_volta_ao_portal(cliente, base_portal):
    _locatario(cliente)
    resposta = _troca(cliente)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/portal"
    cliente_id, contrato, km, foto, nota, multa = base_portal.registros[0]
    assert (cliente_id, contrato, km) == (base_portal.dados["cliente_id"], CONTRATO_PORTAL, "12300")
    assert foto == ("painel.jpg", JPG) and nota == ("nota.png", PNG) and multa == Decimal("50")
    assert "Troca de óleo registrada. Obrigado!" in cliente.get("/portal").text


def test_troca_fora_do_intervalo_mostra_a_multa(cliente, base_portal):
    _locatario(cliente)
    base_portal.resultado = {"excedeu": True, "multa_valor": "50.00"}
    _troca(cliente, km="13.000")
    pagina = cliente.get("/portal").text
    assert "passou do intervalo previsto" in pagina and "R$ 50,00" in pagina


def test_erros_por_campo_nao_gravam_e_preservam_o_km(cliente, base_portal):
    _locatario(cliente)
    resposta = _troca(cliente, km="11.000", arquivos=_fotos(foto=("a.gif", b"GIF89a", "image/gif"), nota=None))
    html = resposta.text
    assert resposta.status_code == 422 and base_portal.registros == []
    assert "Corrija os campos destacados." in html and 'aria-invalid="true"' in html
    assert "não pode ser menor que o último registrado (12000 km)" in html and 'value="11.000"' in html
    assert "Extensão não permitida" in html and "anexe a foto do óleo" in html and "escolha-as de novo" in html
    assert html.count("Corrija os campos destacados.") == 1  # só o formulário da moto que errou
    assert "Olá, Ana" in html  # a página inteira volta, com o cabeçalho


def test_foto_grande_demais_e_recusada(cliente, base_portal):
    _locatario(cliente)
    grande = b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024 + 1)
    resposta = _troca(cliente, arquivos=_fotos(foto=("grande.jpg", grande, "image/jpeg")))
    assert resposta.status_code == 422 and "mais de 10 MB" in resposta.text and base_portal.registros == []


def test_contrato_de_outra_pessoa_ou_invalido_da_404_e_nada_e_gravado(cliente, base_portal):
    _locatario(cliente)
    assert _troca(cliente, contrato="00000000-0000-0000-0000-0000000000ee").status_code == 404
    assert _troca(cliente, contrato="abc").status_code == 404
    assert base_portal.registros == []


def test_moto_sem_plano_nao_aceita_a_troca(cliente, base_portal):
    _locatario(cliente)
    resposta = _troca(cliente, contrato=CONTRATO_PORTAL_SEM_PLANO, km="6000")
    assert resposta.status_code == 422 and "ainda não foi configurado" in resposta.text and base_portal.registros == []


def test_regra_de_negocio_da_rpc_aparece_no_formulario(cliente, base_portal):
    _locatario(cliente)
    base_portal.falhar_com = ValueError("Contrato não está ativo.")
    resposta = _troca(cliente)
    assert resposta.status_code == 422 and "Contrato não está ativo." in resposta.text


def test_troca_exige_csrf(cliente, base_portal):
    _locatario(cliente)
    assert _troca(cliente, token="errado").status_code == 403 and base_portal.registros == []


def test_altera_a_senha_com_o_token_da_propria_sessao(cliente, servico, base_portal):
    _locatario(cliente)
    resposta = cliente.post("/portal/senha", data={"csrf_token": _token(cliente), "nova": SENHA_NOVA, "confirmacao": SENHA_NOVA},
                            follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/portal"
    assert len(servico.senhas) == 1 and servico.senhas[0][1] == SENHA_NOVA and servico.senhas[0][0].startswith("access-")
    assert "Senha alterada." in cliente.get("/portal").text


def test_senha_invalida_volta_com_o_erro_no_campo_e_sem_repetir_a_senha(cliente, servico, base_portal):
    _locatario(cliente)
    token = _token(cliente)
    casos = [
        ("abc12345", "outra1234", "As senhas não conferem."),
        ("abc12", "abc12", "pelo menos 8 caracteres"),
        ("12345678", "12345678", "só números"),
        ("x12345678909x", "x12345678909x", "conter o seu CPF"),
    ]
    for nova, confirmacao, trecho in casos:
        resposta = cliente.post("/portal/senha", data={"csrf_token": token, "nova": nova, "confirmacao": confirmacao})
        assert resposta.status_code == 422 and trecho in resposta.text and 'aria-invalid="true"' in resposta.text
        assert nova not in resposta.text and "<details class=\"cartao\" open>" in resposta.text  # a senha nunca volta na página
    assert servico.senhas == []


def test_senha_recusada_pelo_supabase_aparece_no_campo(cliente, servico, base_portal):
    from src.services.autenticacao import SenhaNaoAlterada

    _locatario(cliente)
    servico.senha_recusada = SenhaNaoAlterada("Escolha uma senha diferente da atual.")
    resposta = cliente.post("/portal/senha", data={"csrf_token": _token(cliente), "nova": SENHA_NOVA, "confirmacao": SENHA_NOVA})
    assert resposta.status_code == 422 and "Escolha uma senha diferente da atual." in resposta.text and SENHA_NOVA not in resposta.text


def test_senha_exige_csrf(cliente, servico, base_portal):
    _locatario(cliente)
    resposta = cliente.post("/portal/senha", data={"csrf_token": "errado", "nova": SENHA_NOVA, "confirmacao": SENHA_NOVA})
    assert resposta.status_code == 403 and servico.senhas == []
