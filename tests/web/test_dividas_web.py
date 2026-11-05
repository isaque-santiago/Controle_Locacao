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


def _compra(cliente, acao="previa", **extra):
    from tests.web.conftest import csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), "acao": acao, "credor": "Celta", "valor_entrada": "5.000,00", "numero_parcelas": "9",
             "valor_parcela": "1.000,00", "primeira_parcela": "2026-05-28", "parcelas_pagas": "6", "data_entrada": "", "conta_id": "",
             "moto_id": "", "descricao": "", "observacoes": "", **extra}
    return cliente.post("/dividas/nova", data=dados, follow_redirects=False)


def test_formulario_de_compra_parcelada_vem_com_os_padroes(cliente):
    entrar(cliente)
    resposta = cliente.get("/dividas/nova")
    html = resposta.text
    assert resposta.status_code == 200 and "Nova compra parcelada" in html
    assert 'name="credor"' in html and 'value="0,00"' in html and 'name="acao" value="previa"' in html
    assert 'name="acao" value="criar"' not in html
    assert "OID-7656 · Celta &lt;b&gt;LS&lt;/b&gt;" in html and "Quezia &lt;i&gt;Silva&lt;/i&gt;" in html


def test_nova_nao_cai_na_ficha_da_divida(cliente):
    entrar(cliente)
    assert cliente.get("/dividas/nova").status_code == 200


def test_conferir_mostra_total_saldo_e_calendario_sem_gravar(cliente, base_dividas):
    entrar(cliente)
    resposta = _compra(cliente)
    html = resposta.text
    assert resposta.status_code == 200 and base_dividas.compras == []
    assert "Confira antes de cadastrar" in html and "R$ 14.000,00" in html and "R$ 3.000,00" in html
    assert "28/05/2026" in html and "28/01/2027" in html and "6 já paga(s)" in html
    assert 'name="acao" value="criar"' in html and 'value="Celta"' in html


def test_cadastrar_grava_com_o_total_calculado_e_abre_a_ficha(cliente, base_dividas):
    from datetime import date
    from decimal import Decimal
    from tests.web.conftest import CONTA_ID, DIVIDA_ID, MOTO_DIVIDA_ID

    entrar(cliente)
    resposta = _compra(cliente, "criar", conta_id=CONTA_ID, moto_id=MOTO_DIVIDA_ID, descricao="Celta 2008")
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_ID}"
    dados = base_dividas.compras[0]
    assert dados["credor"] == "Celta" and dados["valor_total"] == Decimal("14000.00") and dados["valor_entrada"] == Decimal("5000.00")
    assert dados["numero_parcelas"] == 9 and dados["parcelas_pagas"] == 6 and dados["primeira_parcela"] == date(2026, 5, 28)
    assert dados["conta_id"] == CONTA_ID and dados["moto_id"] == MOTO_DIVIDA_ID and dados["descricao"] == "Celta 2008"
    assert "Compra parcelada de Celta cadastrada: 9 parcelas, total de R$ 14.000,00." in cliente.get(f"/dividas/{DIVIDA_ID}").text


def test_campos_invalidos_nao_gravam_e_preservam_o_digitado(cliente, base_dividas):
    entrar(cliente)
    resposta = _compra(cliente, "criar", credor="", numero_parcelas="0", valor_parcela="abc", parcelas_pagas="10")
    html = resposta.text
    assert resposta.status_code == 422 and base_dividas.compras == []
    assert "Credor: informe a quem se deve." in html and "Número de parcelas" in html and "Valor da parcela" in html
    assert 'value="abc"' in html and 'value="5.000,00"' in html


def test_parcelas_pagas_acima_do_total_e_recusada_ja_na_conferencia(cliente, base_dividas):
    entrar(cliente)
    resposta = _compra(cliente, parcelas_pagas="12")
    assert resposta.status_code == 422 and "no máximo 9" in resposta.text and "Confira antes de cadastrar" not in resposta.text


def test_conta_ou_moto_que_nao_existe_e_recusada(cliente, base_dividas):
    entrar(cliente)
    resposta = _compra(cliente, "criar", conta_id="00000000-0000-0000-0000-00000000ffff", moto_id="00000000-0000-0000-0000-00000000fffe")
    assert resposta.status_code == 422 and base_dividas.compras == []
    assert "Conta: escolha uma das opções" in resposta.text and "Moto: escolha uma das opções" in resposta.text


def test_cadastro_sem_csrf_e_recusado(cliente, base_dividas):
    entrar(cliente)
    resposta = cliente.post("/dividas/nova", data={"acao": "criar", "credor": "X"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.compras == []


def test_falha_do_banco_ao_cadastrar_mostra_erro_e_mantem_o_formulario(cliente, base_dividas):
    entrar(cliente)
    base_dividas.falhar_com = RuntimeError("banco fora do ar")
    resposta = _compra(cliente, "criar")
    assert resposta.status_code in (500, 503) and 'value="Celta"' in resposta.text


def test_nova_exige_login(cliente):
    assert cliente.get("/dividas/nova").status_code == 303


def test_lista_leva_ao_cadastro(cliente):
    entrar(cliente)
    assert 'href="/dividas/nova"' in cliente.get("/dividas").text


# ---------------------------------------------------------------- nova dívida (outros tipos) --


def _divida_nova(cliente, **extra):
    from tests.web.conftest import csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), "tipo": "moto_fiado", "credor": "Nilson", "valor_original": "9.675,00",
             "numero_parcelas": "", "valor_parcela": "", "dia_vencimento": "", "saldo_confirmado": "", "moto_id": "",
             "descricao": "", "observacoes": "", **extra}
    return cliente.post("/dividas/nova-divida", data=dados, follow_redirects=False)


def test_formulario_de_nova_divida_oferece_os_cinco_tipos(cliente):
    entrar(cliente)
    html = cliente.get("/dividas/nova-divida").text
    assert "Nova dívida" in html and 'name="tipo"' in html and 'name="saldo_confirmado"' in html
    for rotulo in ("Moto fiado", "Financiamento", "Fornecedor", "Rastreador", "Empréstimo"):
        assert rotulo in html
    assert "Compra parcelada</option>" not in html
    assert "OID-7656 · Celta &lt;b&gt;LS&lt;/b&gt;" in html


def test_nova_divida_nao_cai_na_ficha(cliente):
    entrar(cliente)
    assert cliente.get("/dividas/nova-divida").status_code == 200


def test_cadastrar_divida_grava_e_abre_a_ficha(cliente, base_dividas):
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_ID, MOTO_DIVIDA_ID

    entrar(cliente)
    resposta = _divida_nova(cliente, tipo="financiamento", credor="Nicolas", valor_original="21.901,92", numero_parcelas="24",
                            valor_parcela="912,58", dia_vencimento="28", saldo_confirmado="20.989,34", moto_id=MOTO_DIVIDA_ID)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_ID}"
    d = base_dividas.dividas_criadas[0]
    assert d["tipo"] == "financiamento" and d["credor"] == "Nicolas" and d["valor_original"] == Decimal("21901.92")
    assert d["numero_parcelas"] == 24 and d["valor_parcela"] == Decimal("912.58") and d["dia_vencimento"] == 28
    assert d["saldo_confirmado"] == Decimal("20989.34") and d["moto_id"] == MOTO_DIVIDA_ID
    assert "Dívida cadastrada: Financiamento com Nicolas." in cliente.get(f"/dividas/{DIVIDA_ID}").text


def test_divida_simples_so_com_credor_e_valor(cliente, base_dividas):
    entrar(cliente)
    assert _divida_nova(cliente).status_code == 303
    d = base_dividas.dividas_criadas[0]
    assert d["numero_parcelas"] is None and d["saldo_confirmado"] is None and d["moto_id"] is None


def test_divida_invalida_nao_grava_e_preserva_o_digitado(cliente, base_dividas):
    entrar(cliente)
    resposta = _divida_nova(cliente, tipo="compra_parcelada", credor="", numero_parcelas="10", dia_vencimento="40")
    html = resposta.text
    assert resposta.status_code == 422 and base_dividas.dividas_criadas == []
    assert "Tipo: escolha uma das opções" in html and "Credor: informe a quem se deve." in html
    assert "Valor da parcela" in html and "Dia do vencimento" in html and 'value="9.675,00"' in html


def test_nova_divida_sem_csrf_e_recusada(cliente, base_dividas):
    entrar(cliente)
    resposta = cliente.post("/dividas/nova-divida", data={"tipo": "emprestimo", "credor": "X"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.dividas_criadas == []


def test_falha_do_banco_ao_cadastrar_divida_mostra_erro(cliente, base_dividas):
    entrar(cliente)
    base_dividas.falhar_com = RuntimeError("banco fora do ar")
    resposta = _divida_nova(cliente)
    assert resposta.status_code in (500, 503) and 'value="Nilson"' in resposta.text


def test_lista_tem_os_dois_botoes_de_cadastro(cliente):
    entrar(cliente)
    html = cliente.get("/dividas").text
    assert 'href="/dividas/nova-divida"' in html and 'href="/dividas/nova"' in html


# ---------------------------------------------------------------- pagamento direto (sem parcela) --


def _pagar_direto(cliente, divida_id=None, **extra):
    from tests.web.conftest import DIVIDA_FIADO_ID, csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), "data": "2026-11-04", "valor": "300,00", "conta_id": "", "observacoes": "", **extra}
    return cliente.post(f"/dividas/{divida_id or DIVIDA_FIADO_ID}/pagar", data=dados, follow_redirects=False)


def test_ficha_sem_parcelas_oferece_registrar_pagamento_e_com_parcelas_nao(cliente):
    from tests.web.conftest import DIVIDA_FIADO_ID, DIVIDA_ID

    entrar(cliente)
    assert f'href="/dividas/{DIVIDA_FIADO_ID}/pagar"' in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text
    assert f'href="/dividas/{DIVIDA_ID}/pagar"' not in cliente.get(f"/dividas/{DIVIDA_ID}").text


def test_formulario_de_pagamento_direto_mostra_o_saldo(cliente):
    from tests.web.conftest import DIVIDA_FIADO_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/pagar").text
    assert "Registrar pagamento" in html and "Nilson" in html and "R$ 7.600,00" in html and 'value="7.600,00"' in html


def test_pagamento_direto_grava_e_volta_para_a_ficha(cliente, base_dividas):
    from datetime import date
    from decimal import Decimal
    from tests.web.conftest import CONTA_ID, DIVIDA_FIADO_ID

    entrar(cliente)
    resposta = _pagar_direto(cliente, conta_id=CONTA_ID, observacoes="pix")
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_FIADO_ID}"
    assert base_dividas.pagamentos_diretos == [(DIVIDA_FIADO_ID, date(2026, 11, 4), Decimal("300.00"), CONTA_ID, "pix")]
    assert "Pagamento de R$ 300,00 registrado. A dívida continua em aberto" in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text


def test_pagamento_direto_do_saldo_todo_quita(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_FIADO_ID

    entrar(cliente)
    _pagar_direto(cliente, valor="7.600,00")
    assert "Dívida quitada." in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text


def test_pagamento_direto_acima_do_saldo_e_recusado(cliente, base_dividas):
    entrar(cliente)
    resposta = _pagar_direto(cliente, valor="8.000,00")
    assert resposta.status_code == 422 and base_dividas.pagamentos_diretos == []
    assert "não pode ser maior que o saldo da dívida (R$ 7.600,00)" in resposta.text


def test_divida_com_parcelas_manda_pagar_pela_parcela(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    resposta = cliente.get(f"/dividas/{DIVIDA_ID}/pagar", follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_ID}"
    assert "pague pela parcela" in cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert _pagar_direto(cliente, DIVIDA_ID).status_code == 303 and base_dividas.pagamentos_diretos == []


def test_divida_quitada_nao_recebe_pagamento_direto(cliente, base_dividas):
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_FIADO_ID

    base_dividas.fichas[DIVIDA_FIADO_ID]["saldo"] = Decimal("0")
    entrar(cliente)
    resposta = cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/pagar", follow_redirects=False)
    assert resposta.status_code == 303 and "já está quitada" in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text
    assert 'href="/dividas/' + DIVIDA_FIADO_ID + '/pagar"' not in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text


def test_pagamento_direto_inexistente_sem_csrf_e_sem_login(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_FIADO_ID

    assert cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/pagar").status_code == 303
    entrar(cliente)
    assert cliente.get("/dividas/00000000-0000-0000-0000-0000000000ff/pagar").status_code == 404
    assert cliente.get("/dividas/xyz/pagar").status_code == 404
    resposta = cliente.post(f"/dividas/{DIVIDA_FIADO_ID}/pagar", data={"data": "2026-11-04", "valor": "10"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.pagamentos_diretos == []


# ---------------------------------------------------------------- confirmar saldo --


def _saldo(cliente, divida_id=None, **extra):
    from tests.web.conftest import DIVIDA_FIADO_ID, csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), "acao": "confirmar", "saldo": "3.425,00", "data": "2026-10-16", **extra}
    return cliente.post(f"/dividas/{divida_id or DIVIDA_FIADO_ID}/saldo", data=dados, follow_redirects=False)


def test_ficha_tem_os_botoes_editar_e_confirmar_saldo(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}").text
    assert f'href="/dividas/{DIVIDA_ID}/editar"' in html and f'href="/dividas/{DIVIDA_ID}/saldo"' in html


def test_formulario_de_saldo_parte_do_saldo_atual(cliente):
    from tests.web.conftest import DIVIDA_FIADO_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/saldo").text
    assert "Confirmar saldo" in html and "Nilson" in html and 'value="7.600,00"' in html and "(calculado)" in html
    assert "Remover confirmação" not in html


def test_confirmar_saldo_grava_valor_e_data_e_avisa(cliente, base_dividas):
    from datetime import date
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_FIADO_ID

    entrar(cliente)
    resposta = _saldo(cliente)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_FIADO_ID}"
    assert base_dividas.saldos == [(DIVIDA_FIADO_ID, Decimal("3425.00"), date(2026, 10, 16))]
    assert "Saldo confirmado em R$ 3.425,00" in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text


def test_saldo_zero_e_aceito(cliente, base_dividas):
    entrar(cliente)
    assert _saldo(cliente, saldo="0").status_code == 303 and base_dividas.saldos[0][1] == 0


def test_remover_confirmacao_so_aparece_quando_ha_e_limpa_sem_validar(cliente, base_dividas):
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_FIADO_ID

    base_dividas.fichas[DIVIDA_FIADO_ID]["saldo_confirmado"] = Decimal("3425.00")
    entrar(cliente)
    assert "Remover confirmação" in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/saldo").text
    resposta = _saldo(cliente, acao="limpar", saldo="", data="")
    assert resposta.status_code == 303 and base_dividas.saldos == [(DIVIDA_FIADO_ID, None, None)]
    assert "Confirmação removida" in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text


def test_saldo_invalido_ou_com_data_futura_nao_grava(cliente, base_dividas):
    entrar(cliente)
    resposta = _saldo(cliente, saldo="abc", data="2999-01-01")
    assert resposta.status_code == 422 and base_dividas.saldos == []
    assert "Saldo confirmado" in resposta.text and "não pode ser no futuro" in resposta.text and 'value="abc"' in resposta.text


def test_saldo_404_csrf_e_login(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_FIADO_ID

    assert cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/saldo").status_code == 303
    entrar(cliente)
    assert cliente.get("/dividas/00000000-0000-0000-0000-0000000000ff/saldo").status_code == 404
    assert cliente.get("/dividas/xyz/saldo").status_code == 404
    resposta = cliente.post(f"/dividas/{DIVIDA_FIADO_ID}/saldo", data={"saldo": "1", "data": "2026-10-16"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.saldos == []


def test_falha_do_banco_ao_confirmar_saldo(cliente, base_dividas):
    entrar(cliente)
    base_dividas.falhar_com = RuntimeError("banco fora do ar")
    resposta = _saldo(cliente)
    assert resposta.status_code in (500, 503) and 'value="3.425,00"' in resposta.text


# ---------------------------------------------------------------- editar dívida --


def _editar(cliente, divida_id=None, **extra):
    from tests.web.conftest import DIVIDA_FIADO_ID, csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), "credor": "Nilson (confirmado)", "valor_original": "9.000,00", "dia_vencimento": "10",
             "numero_parcelas": "", "valor_parcela": "", "moto_id": "", "descricao": "Bros e Pop", "observacoes": "", **extra}
    return cliente.post(f"/dividas/{divida_id or DIVIDA_FIADO_ID}/editar", data=dados, follow_redirects=False)


def test_formulario_de_editar_parte_dos_dados_da_divida(cliente):
    from tests.web.conftest import DIVIDA_FIADO_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/editar").text
    assert "Editar dívida" in html and 'value="Nilson"' in html and 'value="9.675,00"' in html
    assert 'name="valor_original"' in html and 'name="numero_parcelas"' in html


def test_editar_a_compra_parcelada_esconde_valores_e_parcelas(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}/editar").text
    assert 'name="credor"' in html and 'name="descricao"' in html and 'name="moto_id"' in html
    assert 'name="valor_original"' not in html and 'name="numero_parcelas"' not in html and "seguem o calendário" in html


def test_editar_grava_e_volta_para_a_ficha(cliente, base_dividas):
    from decimal import Decimal
    from tests.web.conftest import DIVIDA_FIADO_ID

    entrar(cliente)
    resposta = _editar(cliente)
    assert resposta.status_code == 303 and resposta.headers["location"] == f"/dividas/{DIVIDA_FIADO_ID}"
    divida_id, dados = base_dividas.edicoes[0]
    assert divida_id == DIVIDA_FIADO_ID and dados["credor"] == "Nilson (confirmado)" and dados["valor_original"] == Decimal("9000.00")
    assert dados["dia_vencimento"] == 10 and dados["descricao"] == "Bros e Pop" and dados["observacoes"] is None
    assert "Dívida de Nilson (confirmado) atualizada." in cliente.get(f"/dividas/{DIVIDA_FIADO_ID}").text


def test_editar_a_compra_parcelada_so_manda_os_campos_de_identificacao(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    assert _editar(cliente, DIVIDA_ID, valor_original="1", numero_parcelas="3", valor_parcela="5").status_code == 303
    assert set(base_dividas.edicoes[0][1]) == {"credor", "moto_id", "descricao", "observacoes"}


def test_editar_com_erro_nao_grava_e_preserva_o_digitado(cliente, base_dividas):
    entrar(cliente)
    resposta = _editar(cliente, credor="", valor_original="-5", dia_vencimento="40")
    assert resposta.status_code == 422 and base_dividas.edicoes == []
    assert "Credor: informe a quem se deve." in resposta.text and "Valor original" in resposta.text and 'value="-5"' in resposta.text


def test_editar_404_csrf_e_login(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_FIADO_ID

    assert cliente.get(f"/dividas/{DIVIDA_FIADO_ID}/editar").status_code == 303
    entrar(cliente)
    assert cliente.get("/dividas/00000000-0000-0000-0000-0000000000ff/editar").status_code == 404
    resposta = cliente.post(f"/dividas/{DIVIDA_FIADO_ID}/editar", data={"credor": "X"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.edicoes == []


def test_falha_do_banco_ao_editar(cliente, base_dividas):
    entrar(cliente)
    base_dividas.falhar_com = RuntimeError("banco fora do ar")
    resposta = _editar(cliente)
    assert resposta.status_code in (500, 503) and 'value="Nilson (confirmado)"' in resposta.text


# ---------------------------------------------------------------- apagar --


def _apagar(cliente, divida_id=None, confirmar=True, **extra):
    from tests.web.conftest import DIVIDA_ID, csrf_da_sessao

    dados = {"csrf_token": csrf_da_sessao(cliente), **({"confirmar": "sim"} if confirmar else {}), **extra}
    return cliente.post(f"/dividas/{divida_id or DIVIDA_ID}/apagar", data=dados, follow_redirects=False)


def test_pagina_de_apagar_mostra_o_que_sai_junto_e_nao_apaga(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    html = cliente.get(f"/dividas/{DIVIDA_ID}/confirmar-exclusao").text
    assert "Apagar dívida" in html and "Isto não pode ser desfeito" in html
    assert "<b>3</b> parcelas" in html and "<b>2</b> pagamentos" in html and "R$ 11.000,00" in html
    assert 'name="confirmar" value="sim" required' in html and base_dividas.apagadas == []


def test_ficha_tem_o_botao_apagar(cliente):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    assert f'href="/dividas/{DIVIDA_ID}/confirmar-exclusao"' in cliente.get(f"/dividas/{DIVIDA_ID}").text


def test_apagar_com_confirmacao_apaga_e_volta_para_a_lista(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID

    entrar(cliente)
    resposta = _apagar(cliente)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/dividas"
    assert base_dividas.apagadas == [DIVIDA_ID]
    assert "apagada, com as parcelas e os pagamentos" in cliente.get("/dividas").text


def test_apagar_sem_marcar_a_confirmacao_nao_apaga(cliente, base_dividas):
    entrar(cliente)
    resposta = _apagar(cliente, confirmar=False)
    assert resposta.status_code == 422 and base_dividas.apagadas == [] and "Marque a confirmação" in resposta.text


def test_nenhum_get_de_dividas_tem_apagar_no_caminho_e_o_apagar_so_aceita_post(cliente):
    entrar(cliente)
    from tests.web.conftest import DIVIDA_ID

    assert cliente.get(f"/dividas/{DIVIDA_ID}/apagar").status_code == 405


def test_apagar_404_csrf_e_login(cliente, base_dividas):
    from tests.web.conftest import DIVIDA_ID

    assert cliente.get(f"/dividas/{DIVIDA_ID}/confirmar-exclusao").status_code == 303
    entrar(cliente)
    assert cliente.get("/dividas/00000000-0000-0000-0000-0000000000ff/confirmar-exclusao").status_code == 404
    assert _apagar(cliente, "00000000-0000-0000-0000-0000000000ff").status_code == 404
    resposta = cliente.post(f"/dividas/{DIVIDA_ID}/apagar", data={"confirmar": "sim"}, follow_redirects=False)
    assert resposta.status_code in (400, 403) and base_dividas.apagadas == []


def test_falha_do_banco_ao_apagar_mantem_a_pagina(cliente, base_dividas):
    entrar(cliente)
    base_dividas.falhar_com = RuntimeError("banco fora do ar")
    resposta = _apagar(cliente)
    assert resposta.status_code in (500, 503) and base_dividas.apagadas == [] and "Apagar dívida" in resposta.text
