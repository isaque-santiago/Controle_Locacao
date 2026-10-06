"""Formulários de moto em diálogo: cadastrar, editar, atualizar km, inativar/reativar e regularizar documento."""

import re
from datetime import date

from tests.web.conftest import csrf_da_sessao, entrar

MOTO = "00000000-0000-0000-0000-000000000001"  # alugada, com contrato ativo
DISPONIVEL = "00000000-0000-0000-0000-000000000002"
INATIVA = "00000000-0000-0000-0000-000000000003"
NOVA = "00000000-0000-0000-0000-0000000000aa"
DOC = "00000000-0000-0000-0000-0000000000d1"
HX = {"HX-Request": "true", "HX-Target": "form-dialogo"}

CADASTRO = {
    "placa": "abc-1d23", "marca": "Honda", "modelo": "CG 160", "renavam": "", "chassi": "", "cor": "Azul",
    "ano_fabricacao": "2024", "ano_modelo": "2024", "km_atual": "0",
    "valor_aquisicao": "12.500,00", "valor_locacao_sugerido": "320,00", "data_aquisicao": "", "observacoes": "",
}


def _logado(cliente):
    entrar(cliente)
    return csrf_da_sessao(cliente)


def _post(cliente, url, dados, htmx=True):
    return cliente.post(url, data=dados, headers=HX if htmx else {})


# ----------------------------------------------------------------- acesso --

def test_formularios_exigem_login_e_dono(cliente):
    for url in ("/motos/nova", f"/motos/{MOTO}/editar", f"/motos/{MOTO}/km"):
        assert cliente.get(url).status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    for url in ("/motos/nova", f"/motos/{MOTO}/editar", f"/motos/{MOTO}/km"):
        assert cliente.get(url).status_code == 403


def test_post_sem_token_csrf_e_recusado_e_nao_grava(cliente, acoes_motos_falsas):
    _logado(cliente)
    for url in ("/motos/nova", f"/motos/{MOTO}/editar", f"/motos/{MOTO}/km", f"/motos/{DISPONIVEL}/situacao"):
        assert _post(cliente, url, CADASTRO).status_code == 403
    assert acoes_motos_falsas.chamadas == []


def test_locatario_nao_grava(cliente, acoes_motos_falsas):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert _post(cliente, "/motos/nova", CADASTRO).status_code == 403
    assert acoes_motos_falsas.chamadas == []


def test_nova_nao_e_confundida_com_a_ficha(cliente):
    _logado(cliente)
    html = cliente.get("/motos/nova", headers=HX).text
    assert "<html" not in html and 'id="form-dialogo"' in html and "Nova moto" in html


# ------------------------------------------------------------- cadastrar --

def test_formulario_de_cadastro_traz_campos_rotulados_e_padroes(cliente):
    _logado(cliente)
    html = cliente.get("/motos/nova").text
    assert 'hx-post="/motos/nova"' in html and 'name="csrf_token"' in html
    for nome in ("placa", "marca", "modelo", "renavam", "chassi", "cor", "ano_fabricacao", "ano_modelo",
                 "km_atual", "valor_aquisicao", "valor_locacao_sugerido", "data_aquisicao", "observacoes"):
        assert f'name="{nome}"' in html, nome
    ids = set(re.findall(r"<label[^>]*\sfor=\"([^\"]+)\"", html))
    for campo in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
        if 'type="hidden"' not in campo:
            assert re.search(r'\sid="([^"]+)"', campo).group(1) in ids, campo
    assert f'value="{date.today().year}"' in html or 'name="ano_fabricacao"' in html
    assert 'value="0,00"' in html


def test_cadastro_valido_grava_normalizado_e_manda_para_a_ficha(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    resposta = _post(cliente, "/motos/nova", {**CADASTRO, "csrf_token": token})
    assert resposta.status_code == 200
    assert resposta.headers["HX-Redirect"] == f"/motos/{NOVA}"
    (nome, dados), = acoes_motos_falsas.chamadas
    assert nome == "criar_moto"
    assert dados["placa"] == "ABC1D23" and dados["km_atual"] == 0 and dados["valor_locacao_sugerido"] == "320.00"
    assert dados["renavam"] is None and dados["cor"] == "Azul"


def test_aviso_de_confirmacao_aparece_uma_vez_na_proxima_pagina(cliente, base_motos):
    token = _logado(cliente)
    base_motos.motos.append({**base_motos.motos[0], "id": NOVA, "placa": "ABC1D23"})
    _post(cliente, "/motos/nova", {**CADASTRO, "csrf_token": token})
    primeira = cliente.get(f"/motos/{NOVA}").text
    assert "Moto ABC-1D23 cadastrada." in primeira and 'class="aviso sucesso"' in primeira
    assert "cadastrada." not in cliente.get(f"/motos/{NOVA}").text.replace("motos cadastradas", "")


def test_sem_htmx_o_cadastro_redireciona_com_303(cliente):
    token = _logado(cliente)
    resposta = _post(cliente, "/motos/nova", {**CADASTRO, "csrf_token": token}, htmx=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/motos/{NOVA}"


def test_cadastro_invalido_devolve_o_formulario_com_erro_no_campo(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    dados = {**CADASTRO, "csrf_token": token, "placa": "123", "marca": "", "valor_aquisicao": "abc"}
    resposta = _post(cliente, "/motos/nova", dados)
    html = resposta.text
    assert resposta.status_code == 422 and "<html" not in html
    assert "Corrija os campos destacados." in html
    assert 'id="f-placa-erro"' in html and "Placa: use ABC1234 ou ABC1D23." in html
    assert re.search(r'id="f-placa"[^>]*aria-invalid="true"[^>]*aria-describedby="f-placa-erro"', html)
    assert "Marca: informe a marca da moto." in html
    assert 'value="123"' in html  # o que o usuário digitou é mantido
    assert 'class="aviso erro"' in html and 'role="alert"' in html
    assert acoes_motos_falsas.chamadas == []


def test_erro_do_servico_aparece_no_dialogo_sem_perder_os_dados(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    acoes_motos_falsas.falhar_com = ValueError("Já existe uma moto cadastrada com a placa ABC1D23.")
    resposta = _post(cliente, "/motos/nova", {**CADASTRO, "csrf_token": token})
    assert resposta.status_code == 422
    assert "Já existe uma moto cadastrada com a placa ABC1D23." in resposta.text
    assert 'value="Honda"' in resposta.text


def test_falha_inesperada_mostra_mensagem_amigavel_sem_detalhes_tecnicos(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    acoes_motos_falsas.falhar_com = OSError("connection reset by peer 10.0.0.5")
    resposta = _post(cliente, "/motos/nova", {**CADASTRO, "csrf_token": token})
    assert resposta.status_code == 503
    assert "10.0.0.5" not in resposta.text and "tente novamente" in resposta.text


def test_valores_digitados_sao_escapados_ao_voltar_com_erro(cliente):
    token = _logado(cliente)
    resposta = _post(cliente, "/motos/nova", {**CADASTRO, "csrf_token": token, "marca": '"><script>x</script>', "placa": ""})
    assert "<script>x</script>" not in resposta.text and "&lt;script&gt;" in resposta.text


# ----------------------------------------------------------------- editar --

def test_formulario_de_edicao_vem_preenchido_e_sem_km_inicial(cliente):
    _logado(cliente)
    html = cliente.get(f"/motos/{MOTO}/editar").text
    assert "Editar dados da moto" in html and f'hx-post="/motos/{MOTO}/editar"' in html
    assert 'value="ABC-1D01"' in html and 'value="Honda"' in html and 'name="km_atual"' not in html


def test_edicao_grava_sem_km_atual_e_volta_para_a_ficha(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    resposta = _post(cliente, f"/motos/{MOTO}/editar", {**CADASTRO, "csrf_token": token, "cor": "Preta"})
    assert resposta.headers["HX-Redirect"] == f"/motos/{MOTO}"
    (nome, moto_id, dados), = acoes_motos_falsas.chamadas
    assert (nome, moto_id) == ("atualizar_moto", MOTO) and "km_atual" not in dados and dados["cor"] == "Preta"


def test_editar_moto_inexistente_da_404(cliente):
    token = _logado(cliente)
    assert cliente.get("/motos/00000000-0000-0000-0000-0000000000ff/editar").status_code == 404
    assert _post(cliente, "/motos/nao-e-uuid/editar", {**CADASTRO, "csrf_token": token}).status_code == 404


# --------------------------------------------------------------------- km --

def test_formulario_de_km_traz_leitura_atual_e_chave_de_operacao(cliente):
    _logado(cliente)
    html = cliente.get(f"/motos/{MOTO}/km").text
    assert 'value="1000"' in html and "ABC-1D01" in html
    assert re.search(r'name="chave_operacao" value="[0-9a-f-]{36}"', html)
    assert 'name="confirmar_km_menor"' in html


def test_registrar_km_envia_a_chave_para_nao_duplicar(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    chave = "11111111-1111-1111-1111-111111111111"
    resposta = _post(cliente, f"/motos/{MOTO}/km", {"csrf_token": token, "km": "1.500", "chave_operacao": chave})
    assert resposta.headers["HX-Redirect"] == f"/motos/{MOTO}"
    assert acoes_motos_falsas.chamadas == [("registrar_km", MOTO, 1500, False, chave)]


def test_km_menor_so_passa_com_confirmacao(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    _post(cliente, f"/motos/{MOTO}/km", {"csrf_token": token, "km": "10", "confirmar_km_menor": "on"})
    assert acoes_motos_falsas.chamadas[0][1:4] == (MOTO, 10, True)
    acoes_motos_falsas.chamadas.clear()
    acoes_motos_falsas.falhar_com = ValueError("O km informado (10) é menor que o km atual da moto (1000).")
    resposta = _post(cliente, f"/motos/{MOTO}/km", {"csrf_token": token, "km": "10"})
    assert resposta.status_code == 422 and "menor que o km atual" in resposta.text


def test_km_invalido_mostra_erro_no_campo(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    resposta = _post(cliente, f"/motos/{MOTO}/km", {"csrf_token": token, "km": "mil"})
    assert resposta.status_code == 422 and "Nova leitura: use só números inteiros" in resposta.text
    assert acoes_motos_falsas.chamadas == []
    assert re.search(r'name="chave_operacao" value="[0-9a-f-]{36}"', resposta.text)  # a chave é mantida/criada


# -------------------------------------------------------------- situação --

def test_inativar_moto_disponivel(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    resposta = cliente.post(f"/motos/{DISPONIVEL}/situacao", data={"csrf_token": token})
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/motos/{DISPONIVEL}"
    assert acoes_motos_falsas.chamadas == [("alterar_situacao", DISPONIVEL, True)]
    assert "inativada." in cliente.get(f"/motos/{DISPONIVEL}").text


def test_reativar_moto_inativa(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    cliente.post(f"/motos/{INATIVA}/situacao", data={"csrf_token": token})
    assert acoes_motos_falsas.chamadas == [("alterar_situacao", INATIVA, False)]
    assert "reativada." in cliente.get(f"/motos/{INATIVA}").text


def test_moto_alugada_nao_muda_de_situacao(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    cliente.post(f"/motos/{MOTO}/situacao", data={"csrf_token": token})
    assert acoes_motos_falsas.chamadas == []
    assert 'class="aviso erro"' in cliente.get(f"/motos/{MOTO}").text


def test_ficha_mostra_as_acoes_conforme_a_situacao(cliente):
    _logado(cliente)
    alugada = cliente.get(f"/motos/{MOTO}").text
    assert f'hx-get="/motos/{MOTO}/editar"' in alugada and f'hx-get="/motos/{MOTO}/km"' in alugada
    assert "Inativar" not in alugada and "Reativar" not in alugada
    assert "Inativar" in cliente.get(f"/motos/{DISPONIVEL}").text
    assert "Reativar" in cliente.get(f"/motos/{INATIVA}").text


def test_lista_tem_o_botao_nova_moto(cliente):
    _logado(cliente)
    assert 'hx-get="/motos/nova"' in cliente.get("/motos").text


# ------------------------------------------------------------ documentos --

def test_aba_documentos_oferece_regularizar_so_para_pendentes(cliente, base_motos):
    _logado(cliente)
    html = cliente.get(f"/motos/{MOTO}?aba=documentos").text
    assert f'hx-get="/motos/{MOTO}/documentos/{DOC}/regularizar"' in html
    base_motos.documentos[0]["regularizado"] = True
    assert "/regularizar" not in cliente.get(f"/motos/{MOTO}?aba=documentos").text


def test_formulario_de_regularizacao_traz_o_documento_e_a_data_de_hoje(cliente):
    _logado(cliente)
    html = cliente.get(f"/motos/{MOTO}/documentos/{DOC}/regularizar").text
    assert "Regularizar documento" in html and "CRLV" in html and "01/01/2020" in html
    assert f'value="{date.today().isoformat()}"' in html and 'type="date"' in html


def test_regularizar_grava_e_volta_para_a_aba_documentos(cliente, acoes_motos_falsas):
    token = _logado(cliente)
    url = f"/motos/{MOTO}/documentos/{DOC}/regularizar"
    resposta = _post(cliente, url, {"csrf_token": token, "data": "2026-10-06"})
    assert resposta.headers["HX-Redirect"] == f"/motos/{MOTO}?aba=documentos"
    assert acoes_motos_falsas.chamadas == [("regularizar_documento", DOC, date(2026, 10, 6))]
    assert "CRLV 2026 marcado como regularizado." in cliente.get(f"/motos/{MOTO}?aba=documentos").text.replace("Documento ", "")


def test_regularizar_com_data_invalida_ou_documento_ja_regularizado(cliente, acoes_motos_falsas, base_motos):
    token = _logado(cliente)
    url = f"/motos/{MOTO}/documentos/{DOC}/regularizar"
    assert _post(cliente, url, {"csrf_token": token, "data": ""}).status_code == 422
    base_motos.documentos[0]["regularizado"] = True
    resposta = _post(cliente, url, {"csrf_token": token, "data": "2026-10-06"})
    assert resposta.status_code == 422 and "já foi regularizado" in resposta.text
    assert acoes_motos_falsas.chamadas == []


def test_documento_de_outra_moto_ou_id_invalido_da_404(cliente):
    _logado(cliente)
    assert cliente.get(f"/motos/{MOTO}/documentos/00000000-0000-0000-0000-0000000000ee/regularizar").status_code == 404
    assert cliente.get(f"/motos/{MOTO}/documentos/xyz/regularizar").status_code == 404
