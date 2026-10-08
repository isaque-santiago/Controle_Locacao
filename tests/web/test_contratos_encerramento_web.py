"""Fase 3: encerramento de contrato em diálogo HTMX."""

from datetime import date
from decimal import Decimal

from src.domain.vistorias import CHECKLIST_PADRAO
from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true"}


def _url(base, sufixo=""):
    return f"/contratos/{base.id}/encerrar{sufixo}"


def _dados(token, **extra):
    return {"csrf_token": token, "data_encerramento": "2026-10-10", "valor_danos": "0,00", "descricao_danos": "", "confirmar": "on",
            "km": "12000", "nivel_combustivel": "1/2", "adicionais": "", "avarias": "",
            **{f"item_{i}": "ok" for i in CHECKLIST_PADRAO}, **extra}


def test_ficha_do_contrato_ativo_tem_botao_de_encerrar_e_o_encerrado_nao(cliente, base_contratos):
    entrar(cliente)
    assert f'hx-get="/contratos/{base_contratos.id}/encerrar"' in cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Encerrar contrato" not in cliente.get("/contratos/00000000-0000-0000-0000-0000000000d2").text


def test_dialogo_mostra_vistoria_caucao_e_impacto(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get(_url(base_contratos)).text
    assert "Encerrar contrato" in html and "BRA-2E19" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html
    assert 'min="2026-08-01"' in html and 'name="data_encerramento"' in html and 'value="12000"' in html
    assert "início: 10.500 km" in html and "Vistoria de devolução" in html and "Farol dianteiro" in html
    assert "Avarias registradas na vistoria de entrega: freio dianteiro, espelho retrovisor" in html
    assert "Caução recebida R$ 400,00 → devolver ao cliente" in html and "R$ 400,00" in html
    assert "A cobrança abaixo será cancelada:" in html and "20/10/2026" in html
    assert f'hx-post="{_url(base_contratos, "/previa")}"' in html


def test_previa_recalcula_com_danos_e_data(cliente, base_contratos):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    com_danos = cliente.post(_url(base_contratos, "/previa"), data={"data_encerramento": "2026-10-10", "valor_danos": "150,00"},
                             headers={**HX, "X-CSRF-Token": token}).text
    assert "<html" not in com_danos and "− danos R$ 150,00" in com_danos and "R$ 250,00" in com_danos
    excedente = cliente.post(_url(base_contratos, "/previa"), data={"data_encerramento": "2026-10-10", "valor_danos": "500,00"},
                             headers={**HX, "X-CSRF-Token": token}).text
    assert "será criada uma cobrança de" in excedente and "R$ 100,00" in excedente
    depois = cliente.post(_url(base_contratos, "/previa"), data={"data_encerramento": "2026-10-25", "valor_danos": "0"},
                          headers={**HX, "X-CSRF-Token": token}).text
    assert "Nenhuma cobrança será cancelada." in depois
    invalido = cliente.post(_url(base_contratos, "/previa"), data={"data_encerramento": "", "valor_danos": "abc"},
                            headers={**HX, "X-CSRF-Token": token})
    assert invalido.status_code == 200 and "Nenhuma cobrança será cancelada." in invalido.text


def test_encerrar_grava_e_avisa_quanto_devolver(cliente, base_contratos, acoes_contratos_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post(_url(base_contratos), data=_dados(token, valor_danos="150,00", descricao_danos="tanque amassado"), headers=HX)
    assert resposta.status_code == 200 and resposta.headers["HX-Redirect"] == f"/contratos/{base_contratos.id}"
    ((contrato_id, data, vistoria, danos, descricao),) = acoes_contratos_falsas.encerramentos
    assert contrato_id == base_contratos.id and data == date(2026, 10, 10)
    assert danos == Decimal("150.00") and descricao == "tanque amassado"
    assert vistoria["km"] == 12000 and vistoria["nivel_combustivel"] == "1/2" and vistoria["checklist"]["buzina"] == "ok"
    ficha = cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Contrato de Maria &lt;b&gt;Silva&lt;/b&gt; encerrado" in ficha and "Devolver R$ 250,00 de caução" in ficha
    assert "Danos descontados da caução: R$ 150,00" in ficha


def test_encerrar_com_danos_acima_da_caucao_avisa_do_excedente(cliente, base_contratos, acoes_contratos_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    cliente.post(_url(base_contratos), data=_dados(token, valor_danos="500,00", descricao_danos="quadro torto"), headers=HX)
    ficha = cliente.get(f"/contratos/{base_contratos.id}").text
    assert "Devolver R$ 0,00 de caução" in ficha and "R$ 100,00" in ficha


def test_encerrar_com_erros_mantem_o_dialogo_e_nao_grava(cliente, base_contratos, acoes_contratos_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    sem_descricao = cliente.post(_url(base_contratos), data=_dados(token, valor_danos="50,00"), headers=HX)
    assert sem_descricao.status_code == 422 and "Descrição dos danos: informe o que foi danificado." in sem_descricao.text
    varios = {k: v for k, v in _dados(token, data_encerramento="2026-07-01", km="1").items() if k != "confirmar"}
    resposta = cliente.post(_url(base_contratos), data=varios, headers=HX)
    assert resposta.status_code == 422 and 'id="form-dialogo"' in resposta.text
    assert "posterior ao início do contrato" in resposta.text and "Quilometragem da vistoria:" in resposta.text
    assert "Marque a confirmação para encerrar o contrato." in resposta.text and 'value="1"' in resposta.text
    assert acoes_contratos_falsas.encerramentos == []


def test_erro_do_servico_ao_encerrar_mostra_mensagem(cliente, base_contratos, acoes_contratos_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    acoes_contratos_falsas.falhar_com = ValueError("Contrato já encerrado.")
    resposta = cliente.post(_url(base_contratos), data=_dados(token), headers=HX)
    assert resposta.status_code == 422 and "Contrato já encerrado." in resposta.text


def test_contrato_encerrado_ou_inexistente_nao_abre_o_dialogo(cliente, base_contratos):
    entrar(cliente)
    assert cliente.get("/contratos/00000000-0000-0000-0000-0000000000d2/encerrar").status_code == 404
    assert cliente.get("/contratos/00000000-0000-0000-0000-0000000000ff/encerrar").status_code == 404
    token = csrf_da_sessao(cliente)
    assert cliente.post("/contratos/00000000-0000-0000-0000-0000000000d2/encerrar", data=_dados(token)).status_code == 404


def test_encerramento_exige_dono_e_csrf(cliente, base_contratos):
    assert cliente.get(_url(base_contratos)).status_code == 303
    entrar(cliente)
    assert cliente.post(_url(base_contratos), data=_dados("")).status_code in (400, 403)
    assert cliente.post(_url(base_contratos, "/previa"), data={"valor_danos": "0"}).status_code in (400, 403)
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(_url(base_contratos)).status_code == 403


def test_confirmacao_ausente_marca_a_caixa_como_invalida_para_receber_o_foco(cliente, base_contratos):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    dados = {k: v for k, v in _dados(token).items() if k != "confirmar"}
    html = cliente.post(_url(base_contratos), data=dados, headers=HX).text
    assert 'id="f-confirmar-enc"' in html and 'aria-invalid="true" aria-describedby="f-confirmar-enc-erro"' in html
    assert 'id="f-confirmar-enc-erro"' in html
