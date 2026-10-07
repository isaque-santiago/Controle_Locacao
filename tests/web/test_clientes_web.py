"""Fase 3: lista, ficha e formulários de Clientes no app FastAPI."""

from decimal import Decimal

from tests.web.conftest import csrf_da_sessao, entrar

HX = {"HX-Request": "true", "HX-Target": "resultado"}


def test_lista_filtra_busca_e_escapa_dados(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get("/clientes").text
    assert "1 cliente cadastrado" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html
    assert "***.982.***-**" in html and "BRA-2E19" in html
    assert "Maria" not in cliente.get("/clientes?status=inativo").text
    assert "Maria" in cliente.get("/clientes?q=529.982").text
    trecho = cliente.get("/clientes?q=maria", headers=HX).text
    assert "<html" not in trecho and 'class="chips"' in trecho


def test_ficha_tem_abas_e_dados_financeiros(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}").text
    assert "Dados pessoais" in html and "R$ 100,00" in html
    contratos = cliente.get(f"/clientes/{base_clientes.id}?aba=contratos").text
    assert "BRA-2E19" in contratos and "R$ 300,00" in contratos


def test_cadastro_valida_e_grava(cliente, base_clientes, acoes_clientes_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    invalido = cliente.post("/clientes/novo", data={"csrf_token": token, "nome": "", "cpf": "123"}, headers={"HX-Request": "true"})
    assert invalido.status_code == 422 and "CPF: informe um CPF válido" in invalido.text
    resposta = cliente.post("/clientes/novo", data={"csrf_token": token, "nome": "Ana", "cpf": "529.982.247-25", "status": "ativo"}, headers={"HX-Request": "true"})
    assert resposta.headers["HX-Redirect"] == f"/clientes/{base_clientes.id}"
    assert acoes_clientes_falsas[0][0] == "criar"


def test_rotas_de_clientes_exigem_dono(cliente, base_clientes):
    assert cliente.get("/clientes").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/clientes").status_code == 403
    assert cliente.get(f"/clientes/{base_clientes.id}").status_code == 403


def test_resumo_mostra_contrato_ativo_com_proxima_cobranca(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}").text
    assert "Contrato ativo" in html and "BRA-2E19" in html and "desde 01/01/2026" in html
    assert "R$ 300,00" in html and "R$ 500,00" in html and "08/10/2026" in html
    base_clientes.contratos[0]["status"] = "encerrado"
    assert "Nenhum contrato ativo para este cliente." in cliente.get(f"/clientes/{base_clientes.id}").text


def test_aba_portal_sem_acesso_oferece_criar(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=portal").text
    assert "Criar acesso" in html and "Gerar nova senha" not in html
    assert "20/09/2026" in html and "12.500 km" in html and "Cobrada" in html
    assert f"/clientes/{base_clientes.id}/portal/trocas/{base_clientes.troca_id}/painel" in html
    parcial = cliente.get(f"/clientes/{base_clientes.id}/abas/portal").text
    assert "<html" not in parcial and "Trocas de óleo reportadas" in parcial


def test_aba_portal_com_acesso_oferece_senha_e_remocao(cliente, base_clientes):
    base_clientes.clientes[0]["auth_user_id"] = "u1"
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=portal").text
    assert "Acesso ativo ao portal do locatário." in html
    assert "Gerar nova senha" in html and "Remover acesso" in html and "Criar acesso" not in html


def test_criar_acesso_mostra_senha_uma_vez_sem_guardar(cliente, base_clientes, acoes_clientes_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post(f"/clientes/{base_clientes.id}/portal/acesso", headers={"HX-Request": "true", "X-CSRF-Token": token})
    assert resposta.status_code == 200 and "Senha-Temp-123" in resposta.text
    assert "Anote a senha agora" in resposta.text and "no-store" in resposta.headers["cache-control"]
    assert acoes_clientes_falsas[-1] == ("criar_acesso", base_clientes.id)
    assert "Senha-Temp-123" not in cliente.get(f"/clientes/{base_clientes.id}?aba=portal").text


def test_redefinir_senha_e_remover_acesso(cliente, base_clientes, acoes_clientes_falsas):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    cabecalhos = {"HX-Request": "true", "X-CSRF-Token": token}
    nova = cliente.post(f"/clientes/{base_clientes.id}/portal/senha", headers=cabecalhos)
    assert "Senha-Temp-123" in nova.text and acoes_clientes_falsas[-1][0] == "redefinir_senha"
    remocao = cliente.post(f"/clientes/{base_clientes.id}/portal/remover", headers=cabecalhos)
    assert remocao.headers["HX-Redirect"] == f"/clientes/{base_clientes.id}?aba=portal"
    assert acoes_clientes_falsas[-1][0] == "remover_acesso"
    assert "Acesso de Maria &lt;b&gt;Silva&lt;/b&gt; ao portal removido." in cliente.get(f"/clientes/{base_clientes.id}?aba=portal").text


def test_portal_exige_csrf_e_mostra_erro_do_servico(cliente, base_clientes, monkeypatch):
    from src.web import acoes_clientes
    entrar(cliente)
    sem_token = cliente.post(f"/clientes/{base_clientes.id}/portal/acesso", headers={"HX-Request": "true"})
    assert sem_token.status_code in (400, 403)

    def falhar(cliente_id):
        raise ValueError("Este cliente já tem acesso.")
    monkeypatch.setattr(acoes_clientes, "criar_acesso_portal", falhar)
    resposta = cliente.post(f"/clientes/{base_clientes.id}/portal/acesso", headers={"HX-Request": "true", "X-CSRF-Token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 422 and "Este cliente já tem acesso." in resposta.text


def test_foto_da_troca_redireciona_para_url_assinada(cliente, base_clientes):
    entrar(cliente)
    base = f"/clientes/{base_clientes.id}/portal/trocas/{base_clientes.troca_id}"
    resposta = cliente.get(f"{base}/painel")
    assert resposta.status_code == 303 and resposta.headers["location"].startswith("https://storage.exemplo/assinada/c1/painel.jpg")
    assert "c1/nota.jpg" in cliente.get(f"{base}/nota").headers["location"]
    assert cliente.get(f"{base}/outra").status_code == 404
    assert cliente.get(f"/clientes/{base_clientes.id}/portal/trocas/00000000-0000-0000-0000-000000000099/painel").status_code == 404


def test_portal_do_cliente_exige_dono(cliente, base_clientes):
    assert cliente.get(f"/clientes/{base_clientes.id}/portal/trocas/{base_clientes.troca_id}/painel").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(f"/clientes/{base_clientes.id}/portal/trocas/{base_clientes.troca_id}/painel").status_code == 403
    assert cliente.post(f"/clientes/{base_clientes.id}/portal/acesso").status_code == 403


def _muitas_cobrancas(base, quantidade):
    base.cobrancas = [
        {"id": f"p{i}", "vencimento": f"2026-{(i % 9) + 1:02d}-{(i % 27) + 1:02d}", "tipo": "locacao",
         "valor": Decimal("100"), "saldo": Decimal("100"), "situacao": "aberta"}
        for i in range(quantidade)
    ]


def test_pagamentos_pagina_de_dez_em_dez(cliente, base_clientes):
    _muitas_cobrancas(base_clientes, 23)
    entrar(cliente)
    base = f"/clientes/{base_clientes.id}"
    primeira = cliente.get(f"{base}?aba=pagamentos").text
    assert "Mostrando 1 a 10 de 23" in primeira and primeira.count("<tr>") == 10 + 1
    assert f'hx-get="{base}/abas/pagamentos?pagina=2"' in primeira and f'hx-push-url="{base}?aba=pagamentos&amp;pagina=2"' in primeira
    ultima = cliente.get(f"{base}?aba=pagamentos&pagina=3").text
    assert "Mostrando 21 a 23 de 23" in ultima and "pagina=2" in ultima and "pagina=4" not in ultima


def test_pagamentos_parcial_e_pagina_invalida(cliente, base_clientes):
    _muitas_cobrancas(base_clientes, 23)
    entrar(cliente)
    base = f"/clientes/{base_clientes.id}"
    parcial = cliente.get(f"{base}/abas/pagamentos?pagina=2").text
    assert "<html" not in parcial and "Mostrando 11 a 20 de 23" in parcial and 'id="painel-aba"' in parcial
    assert "Mostrando 21 a 23 de 23" in cliente.get(f"{base}/abas/pagamentos?pagina=99").text
    assert "Mostrando 1 a 10 de 23" in cliente.get(f"{base}/abas/pagamentos?pagina=abc").text


def test_pagamentos_curtos_nao_mostram_paginacao_e_totais_ignoram_a_pagina(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{base_clientes.id}?aba=pagamentos").text
    assert "Mostrando" not in html
    _muitas_cobrancas(base_clientes, 23)
    resumo = cliente.get(f"/clientes/{base_clientes.id}?pagina=3").text
    assert "R$ 2.300,00" in resumo  # em aberto soma as 23 parcelas, não só as da página
