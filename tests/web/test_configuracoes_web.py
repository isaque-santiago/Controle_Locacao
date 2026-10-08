"""Fase 3: Configurações (parâmetros do sistema e backup manual)."""

from decimal import Decimal

from tests.web.conftest import csrf_da_sessao, entrar


def _dados(token, **extra):
    return {"csrf_token": token, "multa_atraso_valor": "20,00", "encargo_diario_valor": "8,50", "multa_troca_oleo_valor": "0,00",
            "alerta_manutencao_km": "400", "alerta_manutencao_dias": "20", "alerta_documento_dias": "45", "alerta_cnh_dias": "60", **extra}


def test_pagina_mostra_os_valores_salvos_e_o_exemplo_de_encargos(cliente, base_configuracoes):
    entrar(cliente)
    html = cliente.get("/configuracoes").text
    assert 'value="15,00"' in html and 'value="7,00"' in html and 'value="300"' in html and 'value="30"' in html
    assert "Encargos por atraso" in html and "Alertas de manutenção" in html and "Alertas de documentos e CNH" in html
    # locação de R$ 500, vencida há 5 dias: multa 15 + adicional 5 x 7 = 35, total 550
    assert "R$ 500,00" in html and "5 dias" in html and "multa <span class=\"mono text-texto\">R$ 15,00" in html
    assert "adicional <span class=\"mono text-texto\">R$ 35,00" in html and "encargos <span class=\"mono text-texto\">R$ 50,00" in html and "total a pagar <span class=\"mono font-semibold text-texto\">R$ 550,00" in html
    assert 'action="/configuracoes/backup"' in html and "15 tabelas" in html


def test_salva_e_avisa_quais_campos_mudaram(cliente, base_configuracoes):
    entrar(cliente)
    resposta = cliente.post("/configuracoes", data=_dados(csrf_da_sessao(cliente)), follow_redirects=False)
    assert resposta.status_code == 303 and resposta.headers["location"] == "/configuracoes"
    gravado = base_configuracoes.gravados[0]
    assert gravado["multa_atraso_valor"] == Decimal("20.00") and gravado["encargo_diario_valor"] == Decimal("8.50")
    assert gravado["alerta_manutencao_km"] == 400 and gravado["alerta_cnh_dias"] == 60
    pagina = cliente.get("/configuracoes").text
    assert "Configurações salvas:" in pagina and "Multa de atraso (no vencimento)" in pagina and "CNH do cliente" in pagina
    assert "Multa por troca de óleo" not in pagina.split("Configurações salvas:")[1].split("</")[0]  # não mudou
    assert 'value="20,00"' in pagina and 'value="8,50"' in pagina


def test_salvar_sem_mudar_nada_diz_que_nenhum_valor_foi_alterado(cliente, base_configuracoes):
    entrar(cliente)
    cliente.post("/configuracoes", data=_dados(csrf_da_sessao(cliente), multa_atraso_valor="15,00", encargo_diario_valor="7,00",
                                               alerta_manutencao_km="300", alerta_manutencao_dias="15",
                                               alerta_documento_dias="30", alerta_cnh_dias="30"))
    assert "Nenhum valor foi alterado." in cliente.get("/configuracoes").text


def test_erros_por_campo_nao_gravam_e_preservam_o_digitado(cliente, base_configuracoes):
    entrar(cliente)
    resposta = cliente.post("/configuracoes", data=_dados(csrf_da_sessao(cliente), multa_atraso_valor="abc", alerta_cnh_dias="100001",
                                                         alerta_documento_dias=""))
    html = resposta.text
    assert resposta.status_code == 422 and base_configuracoes.gravados == []
    assert "Corrija os campos destacados." in html and 'aria-invalid="true"' in html
    assert "Multa de atraso (no vencimento): use só números" in html and "o maior valor aceito é 100000" in html
    assert "Documentos da moto (dias)" in html and 'value="abc"' in html and 'value="100001"' in html
    assert 'value="15,00"' not in html  # o formulário mostra o digitado, não o salvo


def test_erro_do_servico_aparece_no_formulario(cliente, base_configuracoes):
    entrar(cliente)
    base_configuracoes.falhar_com = ValueError("Parâmetros em uso por outra operação.")
    resposta = cliente.post("/configuracoes", data=_dados(csrf_da_sessao(cliente)))
    assert resposta.status_code == 422 and "Parâmetros em uso por outra operação." in resposta.text


def test_backup_responde_com_o_zip_para_baixar_sem_cache(cliente, base_configuracoes):
    from src.domain.valores import hoje_br

    entrar(cliente)
    resposta = cliente.post("/configuracoes/backup", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 200 and resposta.headers["content-type"] == "application/zip"
    assert resposta.headers["content-disposition"] == f'attachment; filename="backup-{hoje_br().isoformat()}.zip"'
    assert resposta.headers["cache-control"] == "no-store" and resposta.content.startswith(b"PK") and base_configuracoes.backups == 1


def test_backup_e_salvar_exigem_csrf(cliente, base_configuracoes):
    entrar(cliente)
    assert cliente.post("/configuracoes/backup", data={"csrf_token": "errado"}).status_code == 403
    assert cliente.post("/configuracoes", data=_dados("errado")).status_code == 403
    assert base_configuracoes.backups == 0 and base_configuracoes.gravados == []
    assert cliente.get("/configuracoes/backup").status_code == 405  # o backup nunca sai por GET


def test_configuracoes_exigem_dono(cliente, base_configuracoes):
    assert cliente.get("/configuracoes").status_code == 303
    assert cliente.post("/configuracoes/backup", data={"csrf_token": "x"}).status_code in (303, 403)
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/configuracoes").status_code == 403
    assert cliente.post("/configuracoes", data=_dados("x")).status_code == 403
    assert cliente.post("/configuracoes/backup", data={"csrf_token": "x"}).status_code == 403
    assert base_configuracoes.backups == 0 and base_configuracoes.gravados == []
