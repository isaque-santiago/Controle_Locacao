"""Páginas de Dívidas: acesso e conteúdo."""

from tests.web.conftest import entrar


def test_lista_exige_login(cliente):
    resposta = cliente.get("/dividas")
    assert resposta.status_code == 303 and resposta.headers["location"].startswith("/login")


def test_lista_mostra_totais_em_reais_e_cada_divida(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "<h1>Dívidas</h1>" in html and "2 dívidas em aberto" in html
    assert "R$ 10.600,00" in html and "R$ 7.600,00" in html and "Parcelas atrasadas" in html
    assert "10/10/2026" in html and "Nilson" in html
    assert "R$ 14.000,00" in html and "R$ 11.000,00" in html and "R$ 3.000,00" in html
    assert 'href="/dividas/d2"' in html and "OID-7656" in html


def test_lista_mostra_situacoes_e_saldo_confirmado(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "Parcela atrasada (2)" in html and "Quitada" in html and "Em aberto" in html
    assert "confirmado" in html and "Moto fiado" in html and "Empréstimo" in html


def test_nomes_do_banco_sao_escapados_na_lista(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "Celta <b>Zero</b>" not in html and "Celta &lt;b&gt;Zero&lt;/b&gt;" in html


def test_lista_vazia_mostra_estado_vazio(cliente, base_dividas):
    base_dividas.linhas = []
    base_dividas.totais = {"total_em_aberto": 0, "moto_fiado": 0, "dividas_em_aberto": 0, "parcelas_atrasadas": 0,
                           "proximo_vencimento": None, "proximo_credor": None}
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert "Nenhuma dívida cadastrada" in html and "0 dívidas em aberto" in html


def test_menu_tem_dividas_e_marca_a_pagina_atual(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert 'href="/dividas"' in html and 'aria-current="page"' in html


def test_ficha_mostra_resumo_parcelas_e_pagamentos(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert "Compra parcelada" in html and "OID-7656" in html and "entrada de R$ 5.000,00" in html
    assert "R$ 14.000,00" in html and "R$ 11.000,00" in html and "R$ 3.000,00" in html and "9 x R$ 1.000,00" in html
    assert "vence todo dia 28" in html and "28/11/2026" in html
    assert "Atrasada · 34 d" in html and "A vencer" in html and "Paga" in html
    assert "estimada" in html and "Entrada da compra" in html and "01/05/2026" in html


def test_ficha_so_oferece_pagar_nas_parcelas_em_aberto(cliente):
    from tests.web.conftest import DIVIDA_ID, PARCELA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert f'href="/dividas/parcelas/{PARCELA_ID}/pagar"' in html and 'href="/dividas/parcelas/v9/pagar"' in html
    assert 'href="/dividas/parcelas/v7/pagar"' not in html


def test_ficha_escapa_textos_do_banco(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert "Celta <b>Zero</b>" not in html and "Celta &lt;b&gt;Zero&lt;/b&gt;" in html
    assert "<i>de boca</i>" not in html and "&lt;i&gt;de boca&lt;/i&gt;" in html


def test_ficha_inexistente_ou_com_id_invalido_e_404(cliente):
    entrar(cliente)
    assert cliente.get("/dividas/00000000-0000-0000-0000-0000000000ff").status_code == 404
    assert cliente.get("/dividas/isso-nao-e-um-uuid").status_code == 404


def test_ficha_exige_login(cliente):
    from tests.web.conftest import DIVIDA_ID

    assert cliente.get(f"/dividas/{DIVIDA_ID}").status_code == 303


def test_ficha_com_diferenca_de_saldo_confirmado_avisa(cliente, base_dividas):
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_ID

    f = base_dividas.fichas[DIVIDA_ID]
    f["diferenca"] = Decimal("-1350.00")
    f["saldo_confirmado"] = Decimal("3425.00")
    f["divida"]["confirmado_em"] = "2026-10-16"
    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert "difere do calculado" in html and "confirmado por você em 16/10/2026" in html


def _pagar(cliente, vencimento_id=None, **extra):
    from tests.web.conftest import PARCELA_ID, csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), "data": "2026-11-04", "valor": "1.000,00", "conta_id": "", "observacoes": "", **extra}
    return cliente.post(f"/dividas/parcelas/{vencimento_id or PARCELA_ID}/pagar", data=dados, follow_redirects=False)


def test_formulario_de_pagamento_mostra_a_parcela_e_o_saldo(cliente):
    from tests.web.conftest import PARCELA_ID

    entrar(cliente)
    resposta = cliente.get(f"/dividas/parcelas/{PARCELA_ID}/pagar")
    html = resposta.text
    assert resposta.status_code == 200 and "Pagar parcela" in html
    assert "parcela 8" in html and "28/11/2026" in html and "saldo" in html and 'value="1.000,00"' in html
    assert "Celta &lt;b&gt;Zero&lt;/b&gt;" in html and "Celta <b>Zero</b>" not in html
    assert "Quezia &lt;i&gt;Silva&lt;/i&gt;" in html and "Não informada" in html


def test_pagar_a_parcela_grava_e_volta_para_a_ficha(cliente, base_dividas):
    from datetime import date
    from decimal import Decimal
    from tests.web.conftest import CONTA_ID, DIVIDA_ID, PARCELA_ID

    entrar(cliente)
    resposta = _pagar(cliente, conta_id=CONTA_ID, observacoes="pix do Alisson")
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_ID}"
    assert base_dividas.pagamentos == [(PARCELA_ID, date(2026, 11, 4), Decimal("1000.00"), CONTA_ID, "pix do Alisson")]
    assert "Pagamento de R$ 1.000,00 registrado na parcela 8. Parcela quitada." in cliente.get(f"/dividas/{DIVIDA_ID}").text


def test_pagamento_parcial_avisa_que_a_parcela_continua_aberta(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    assert _pagar(cliente, valor="400").status_code == 303
    assert "A parcela continua em aberto" in cliente.get(f"/dividas/{DIVIDA_ID}").text


def test_valor_maior_que_o_saldo_nao_grava_e_preserva_o_digitado(cliente, base_dividas):
    entrar(cliente)
    resposta = _pagar(cliente, valor="1.500,00", observacoes="tentativa")
    assert resposta.status_code == 422 and base_dividas.pagamentos == []
    assert "não pode ser maior que o saldo da parcela (R$ 1.000,00)" in resposta.text
    assert 'value="1.500,00"' in resposta.text and "tentativa" in resposta.text


def test_conta_que_nao_existe_e_recusada(cliente, base_dividas):
    entrar(cliente)
    resposta = _pagar(cliente, conta_id="00000000-0000-0000-0000-00000000ffff")
    assert resposta.status_code == 422 and base_dividas.pagamentos == [] and "Conta: escolha uma das opções" in resposta.text


def test_pagamento_sem_csrf_e_recusado(cliente, base_dividas):
    from tests.web.conftest import PARCELA_ID

    entrar(cliente)
    resposta = cliente.post(f"/dividas/parcelas/{PARCELA_ID}/pagar", data={"data": "2026-11-04", "valor": "10"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.pagamentos == []


def test_parcela_ja_paga_volta_para_a_ficha_com_aviso(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID, PARCELA_PAGA_ID

    entrar(cliente)
    resposta = cliente.get(f"/dividas/parcelas/{PARCELA_PAGA_ID}/pagar", follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_ID}"
    assert "Essa parcela já está paga." in cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert _pagar(cliente, PARCELA_PAGA_ID).status_code == 303 and base_dividas.pagamentos == []


def test_parcela_inexistente_ou_id_invalido_e_404(cliente):
    entrar(cliente)
    assert cliente.get("/dividas/parcelas/00000000-0000-0000-0000-0000000000ff/pagar").status_code == 404
    assert cliente.get("/dividas/parcelas/xyz/pagar").status_code == 404


def test_falha_do_banco_mostra_erro_e_nao_perde_o_formulario(cliente, base_dividas):
    entrar(cliente)
    base_dividas.falhar_com = RuntimeError("banco fora do ar")
    resposta = _pagar(cliente, valor="250")
    assert resposta.status_code in (500, 503) and 'value="250"' in resposta.text


def test_pagar_exige_login(cliente):
    from tests.web.conftest import PARCELA_ID

    assert cliente.get(f"/dividas/parcelas/{PARCELA_ID}/pagar").status_code == 303
