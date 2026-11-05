"""Fase 3: assistente de novo contrato (quatro etapas) no app FastAPI."""

from src.domain.vistorias import CHECKLIST_PADRAO
from tests.web.conftest import csrf_da_sessao, entrar

BASE = "/contratos/novo"
CONDICOES = {"data_inicio": "2026-10-07", "indeterminado": "on", "periodicidade": "semanal",
             "valor_periodo": "320,00", "caucao_valor": "500,00", "data_fim_prevista": "2026-11-06", "acao": "avancar"}


def _vistoria(**extra):
    return {"km": "5000", "nivel_combustivel": "cheio", "adicionais": "", "avarias": "", "acao": "criar",
            **{f"item_{i}": "ok" for i in CHECKLIST_PADRAO}, **extra}


def _bloco_vinculada(n, moto_id, **extra):
    """Campos da vistoria de entrega da n-ésima moto vinculada (prefixo vinc<n>_ e o id da moto escondido)."""
    campos = {"km": "1000", "nivel_combustivel": "cheio", "adicionais": "", "avarias": "",
              **{f"item_{i}": "ok" for i in CHECKLIST_PADRAO}, **extra}
    return {f"vinc{n}_{chave}": valor for chave, valor in campos.items()} | {f"vinc{n}_moto": moto_id}


def _preparar(cliente, base, ate=4):
    """Percorre o assistente até a etapa `ate` com dados válidos (1 = só cliente, 2 = + moto, 3 = + condições)."""
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    cliente.get(f"{BASE}/iniciar")
    cliente.post(f"{BASE}/cliente", data={"csrf_token": token, "cliente_id": base.cliente["id"]})
    if ate >= 2:
        cliente.post(f"{BASE}/moto", data={"csrf_token": token, "moto_id": base.moto_livre["id"]})
    if ate >= 3:
        cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **CONDICOES})
    return token


def test_iniciar_leva_a_etapa_um_com_clientes_e_marca_elegibilidade(cliente, base_contratos):
    entrar(cliente)
    resposta = cliente.get(f"{BASE}/iniciar")
    assert resposta.status_code == 303 and resposta.headers["location"] == f"{BASE}?etapa=1"
    html = cliente.get(f"{BASE}?etapa=1").text
    assert "Etapa 1 de 4" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html and "***.982.***-**" in html
    assert "Já aluga BRA-2E19" in html and "Bloqueado · não pode alugar" in html
    assert 'aria-label="Escolher Maria' in html
    assert "Selecione um cliente para continuar." in html


def test_etapas_adiante_sao_bloqueadas_ate_escolher(cliente, base_contratos):
    entrar(cliente)
    cliente.get(f"{BASE}/iniciar")
    for etapa in (2, 3, 4):
        resposta = cliente.get(f"{BASE}?etapa={etapa}")
        assert resposta.status_code == 303 and resposta.headers["location"] == f"{BASE}?etapa=1"
    assert cliente.get(f"{BASE}?etapa=abc").status_code == 200  # etapa inválida cai na primeira


def test_busca_de_cliente_por_nome_cpf_e_trecho_parcial(cliente, base_contratos):
    entrar(cliente)
    cliente.get(f"{BASE}/iniciar")
    por_nome = cliente.get(f"{BASE}?etapa=1&q=pedro").text
    assert "Pedro" in por_nome and "Maria" not in por_nome
    assert "Pedro" in cliente.get(f"{BASE}?etapa=1&q=111.444").text
    parcial = cliente.get(f"{BASE}?etapa=1&q=maria", headers={"HX-Request": "true", "HX-Target": "resultado"}).text
    assert "<html" not in parcial and "Maria" in parcial
    assert "Nenhum cliente encontrado" in cliente.get(f"{BASE}?etapa=1&q=zzz").text


def test_escolher_cliente_bloqueado_e_recusado(cliente, base_contratos):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    cliente.get(f"{BASE}/iniciar")
    resposta = cliente.post(f"{BASE}/cliente", data={"csrf_token": token, "cliente_id": base_contratos.cliente_bloqueado["id"]})
    assert resposta.headers["location"] == f"{BASE}?etapa=1"
    assert "Este cliente não pode alugar" in cliente.get(f"{BASE}?etapa=1").text
    assert cliente.get(f"{BASE}?etapa=2").headers["location"] == f"{BASE}?etapa=1"


def test_etapa_dois_lista_so_motos_disponiveis_e_marca_a_escolhida(cliente, base_contratos):
    token = _preparar(cliente, base_contratos, ate=1)
    html = cliente.get(f"{BASE}?etapa=2").text
    assert "QRS-4T21" in html and "R$ 300,00" in html and "Maria &lt;b&gt;Silva&lt;/b&gt;" in html
    assert 'aria-label="Escolher BRA-2E19"' not in html  # a moto alugada não é oferecida
    assert "Selecione uma moto disponível para continuar." in html
    cliente.post(f"{BASE}/moto", data={"csrf_token": token, "moto_id": base_contratos.moto_livre["id"]})
    escolhida = cliente.get(f"{BASE}?etapa=2").text
    assert "Selecionada" in escolhida and f"{BASE}?etapa=3" in escolhida
    recusada = cliente.post(f"{BASE}/moto", data={"csrf_token": token, "moto_id": base_contratos.moto["id"]})
    assert recusada.status_code == 303 and "não está mais disponível" in cliente.get(f"{BASE}?etapa=2").text


def test_vincular_moto_extra_aparece_no_resumo_e_vai_no_payload(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos, ate=2)
    extra = base_contratos.moto_livre2["id"]
    html = cliente.get(f"{BASE}?etapa=2").text
    assert "Vincular ao contrato" in html and 'aria-label="Vincular ao mesmo contrato a moto ABC-1D23"' in html
    resposta = cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": extra, "acao": "vincular"})
    assert resposta.status_code == 303 and resposta.headers["location"] == f"{BASE}?etapa=2"
    html = cliente.get(f"{BASE}?etapa=2").text
    assert "Motos vinculadas (1)" in html and "Vinculada · tirar" in html
    cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **CONDICOES})
    assert "Motos vinculadas (1)" in cliente.get(f"{BASE}?etapa=4").text
    cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(), **_bloco_vinculada(1, extra)})
    dados, _ = acoes_contratos_falsas.chamadas[0]
    assert dados["motos_vinculadas"] == [extra]


def test_remover_moto_extra_e_trocar_principal_descarta_a_vinculada(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos, ate=2)
    extra = base_contratos.moto_livre2["id"]
    cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": extra, "acao": "vincular"})
    cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": extra, "acao": "remover"})
    assert "Motos vinculadas" not in cliente.get(f"{BASE}?etapa=2").text
    cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": extra, "acao": "vincular"})
    cliente.post(f"{BASE}/moto", data={"csrf_token": token, "moto_id": extra})  # vira a principal
    assert "Motos vinculadas" not in cliente.get(f"{BASE}?etapa=2").text


def test_vincular_exige_principal_e_recusa_moto_indisponivel(cliente, base_contratos):
    token = _preparar(cliente, base_contratos, ate=1)
    cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": base_contratos.moto_livre2["id"], "acao": "vincular"})
    assert "Escolha primeiro a moto principal" in cliente.get(f"{BASE}?etapa=1").text
    cliente.post(f"{BASE}/moto", data={"csrf_token": token, "moto_id": base_contratos.moto_livre["id"]})
    cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": base_contratos.moto["id"], "acao": "vincular"})
    assert "não está disponível para vincular" in cliente.get(f"{BASE}?etapa=2").text


PROMESSA = {**CONDICOES, "tipo_contrato": "promessa_compra", "valor_entrada": "1.000,00", "numero_parcelas": "4",
            "parcelas_pagas_inicial": "0", "dia_cobranca": "", "primeira_cobranca": "", "periodicidade": "mensal"}


def test_condicoes_oferecem_tipo_e_campos_da_promessa(cliente, base_contratos):
    _preparar(cliente, base_contratos, ate=2)
    html = cliente.get(f"{BASE}?etapa=3").text
    assert "Tipo do contrato" in html and "Promessa de compra" in html
    for rotulo in ("Entrada", "Número de parcelas", "Parcelas já pagas", "Dia da cobrança", "Primeira cobrança"):
        assert rotulo in html


def test_promessa_confirma_com_total_agenda_limitada_e_payload_completo(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos, ate=2)
    cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **PROMESSA})
    html = cliente.get(f"{BASE}?etapa=4").text
    assert "Total da promessa" in html and "R$ 2.280,00" in html  # 1.000 + 4 x 320
    assert "Parcela 1" in html and "Parcela 5" not in html and "Entrada" in html and "4 parcelas" in html
    assert "Promessa de compra: a prévia mostra só os primeiros 30 dias" in html  # igual à RPC: o resto sai pelo gerador
    assert "Prazo indeterminado: a prévia" not in html
    cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()})
    dados, _ = acoes_contratos_falsas.chamadas[0]
    assert dados["tipo_contrato"] == "promessa_compra" and dados["numero_parcelas"] == 4
    assert dados["valor_entrada"] == "1000.00" and dados["data_fim_prevista"] is None


def test_promessa_sem_parcelas_volta_com_erro_no_campo(cliente, base_contratos):
    token = _preparar(cliente, base_contratos, ate=2)
    resposta = cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **PROMESSA, "numero_parcelas": ""})
    assert resposta.status_code == 422 and "Número de parcelas:" in resposta.text


def test_locacao_comum_nao_envia_campos_de_promessa(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos)
    assert "Total da promessa" not in cliente.get(f"{BASE}?etapa=4").text
    cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()})
    dados, _ = acoes_contratos_falsas.chamadas[0]
    assert "tipo_contrato" not in dados and "numero_parcelas" not in dados


def test_condicoes_comecam_com_padroes_da_moto(cliente, base_contratos):
    _preparar(cliente, base_contratos, ate=2)
    html = cliente.get(f"{BASE}?etapa=3").text
    assert 'value="300,00"' in html and 'value="0,00"' in html  # valor sugerido da moto e caução zerada
    assert "checked" in html and "5.000 km" in html


def test_condicoes_invalidas_voltam_com_erro_por_campo_e_texto_preservado(cliente, base_contratos):
    token = _preparar(cliente, base_contratos, ate=2)
    resposta = cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **CONDICOES, "valor_periodo": "abc", "caucao_valor": "-1"})
    assert resposta.status_code == 422
    assert "Valor do período:" in resposta.text and "Caução:" in resposta.text and 'value="abc"' in resposta.text
    assert cliente.get(f"{BASE}?etapa=4").headers["location"] == f"{BASE}?etapa=3"  # não avançou


def test_voltar_guarda_o_que_foi_digitado_mesmo_invalido(cliente, base_contratos):
    token = _preparar(cliente, base_contratos, ate=2)
    voltar = cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **CONDICOES, "valor_periodo": "12,", "acao": "voltar"})
    assert voltar.headers["location"] == f"{BASE}?etapa=2"
    assert 'value="12,"' in cliente.get(f"{BASE}?etapa=3").text


def test_confirmar_mostra_resumo_agenda_e_vistoria(cliente, base_contratos):
    _preparar(cliente, base_contratos)
    html = cliente.get(f"{BASE}?etapa=4").text
    assert "Maria &lt;b&gt;Silva&lt;/b&gt; vai alugar QRS-4T21" in html and "Semanal" in html and "R$ 320,00" in html
    assert "Prévia da agenda de cobranças" in html and "R$ 500,00" in html and "Parcela 1" in html
    assert "Prazo indeterminado: a prévia mostra só os primeiros 30 dias" in html
    assert "Vistoria de entrega" in html and 'value="5000"' in html and "Farol dianteiro" in html


def test_criar_contrato_grava_e_redireciona_com_aviso(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(avarias="arranhão")})
    assert resposta.status_code == 303 and resposta.headers["location"] == "/contratos/00000000-0000-0000-0000-0000000000e1"
    ((dados, vistoria),) = acoes_contratos_falsas.chamadas
    assert dados["moto_id"] == base_contratos.moto_livre["id"] and dados["cliente_id"] == base_contratos.cliente["id"]
    assert dados["km_inicial"] == 5000 and dados["data_fim_prevista"] is None
    assert dados["valor_periodo"] == "320.00" and dados["caucao_valor"] == "500.00" and dados["periodicidade"] == "semanal"
    assert vistoria["km"] == 5000 and vistoria["avarias"] == "arranhão" and vistoria["checklist"]["farol_dianteiro"] == "ok"
    assert "Contrato de Maria &lt;b&gt;Silva&lt;/b&gt; com a moto QRS-4T21 criado" in cliente.get("/contratos").text
    assert cliente.get(f"{BASE}?etapa=2").headers["location"] == f"{BASE}?etapa=1"  # o rascunho foi descartado


def test_criar_com_vistoria_invalida_nao_grava_e_mostra_erros(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(km="4999", adicionais="sem estado")})
    assert resposta.status_code == 422 and "Quilometragem da vistoria:" in resposta.text and "nome=estado" in resposta.text
    assert 'value="4999"' in resposta.text and acoes_contratos_falsas.chamadas == []


def test_confirmar_oferece_fotos_da_entrega_com_camera_e_envio_multipart(cliente, base_contratos):
    _preparar(cliente, base_contratos)
    html = cliente.get(f"{BASE}?etapa=4").text
    assert 'enctype="multipart/form-data"' in html and 'name="fotos" type="file" multiple accept="image/*"' in html
    assert "Fotos da entrega" in html and "As fotos da vistoria são anexadas depois" not in html
    assert html.count('capture="environment"') == 1 and "Tirar foto agora" in html


def test_criar_com_fotos_anexa_a_vistoria_de_entrega(cliente, base_contratos, acoes_contratos_falsas, monkeypatch):
    from src.web import acoes_vistorias

    enviadas = []
    monkeypatch.setattr(acoes_vistorias, "anexar_fotos_da_entrega",
                        lambda contrato_id, fotos: enviadas.append((contrato_id, [f.filename for f in fotos])) or 1)
    token = _preparar(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()}, follow_redirects=False,
                            files=[("fotos", ("a.jpg", b"\xff\xd8\xff\xe0" + b"0" * 32, "image/jpeg")),
                                   ("fotos", ("b.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png"))])
    assert resposta.status_code == 303 and len(acoes_contratos_falsas.chamadas) == 1
    assert enviadas == [("00000000-0000-0000-0000-0000000000e1", ["a.jpg", "b.png"])]
    aviso = cliente.get("/contratos").text
    assert "1 foto da vistoria de entrega anexada" not in aviso and "Atenção: 1 foto não foi enviada" in aviso


def test_criar_sem_fotos_nao_chama_o_storage_e_avisa_onde_adicionar(cliente, base_contratos, acoes_contratos_falsas, monkeypatch):
    from src.web import acoes_vistorias

    monkeypatch.setattr(acoes_vistorias, "anexar_fotos_da_entrega", lambda *a: pytest.fail("não deveria enviar fotos"))
    token = _preparar(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()}, follow_redirects=False)
    assert resposta.status_code == 303 and "Adicionar fotos" in cliente.get("/contratos").text


def test_foto_invalida_na_entrega_nao_cria_o_contrato(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()},
                            files=[("fotos", ("a.gif", b"GIF89a", "image/gif"))])
    assert resposta.status_code == 422 and "a.gif" in resposta.text and acoes_contratos_falsas.chamadas == []
    assert "escolha as fotos de novo" in resposta.text


def test_erro_do_servico_ao_criar_mostra_mensagem_e_mantem_rascunho(cliente, base_contratos, acoes_contratos_falsas):
    token = _preparar(cliente, base_contratos)
    acoes_contratos_falsas.falhar_com = ValueError("A moto não está disponível.")
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()})
    assert resposta.status_code == 422 and "A moto não está disponível." in resposta.text
    assert cliente.get(f"{BASE}?etapa=4").status_code == 200


def test_voltar_na_confirmacao_guarda_a_vistoria_digitada(cliente, base_contratos):
    token = _preparar(cliente, base_contratos)
    voltar = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(avarias="risco no tanque", acao="voltar")})
    assert voltar.headers["location"] == f"{BASE}?etapa=3"
    assert "risco no tanque" in cliente.get(f"{BASE}?etapa=4").text


def test_cancelar_descarta_o_rascunho(cliente, base_contratos):
    token = _preparar(cliente, base_contratos, ate=2)
    resposta = cliente.post(f"{BASE}/cancelar", data={"csrf_token": token})
    assert resposta.headers["location"] == "/contratos"
    assert cliente.get(f"{BASE}?etapa=2").headers["location"] == f"{BASE}?etapa=1"


def test_assistente_exige_dono_e_csrf(cliente, base_contratos):
    assert cliente.get(BASE).status_code == 303
    entrar(cliente)
    assert cliente.post(f"{BASE}/cliente", data={"cliente_id": base_contratos.cliente["id"]}).status_code in (400, 403)
    assert cliente.post(f"{BASE}/criar", data=_vistoria()).status_code in (400, 403)
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(BASE).status_code == 403 and cliente.get(f"{BASE}/iniciar").status_code == 403


def _com_vinculada(cliente, base):
    token = _preparar(cliente, base, ate=2)
    extra = base.moto_livre2["id"]
    cliente.post(f"{BASE}/moto-extra", data={"csrf_token": token, "moto_id": extra, "acao": "vincular"})
    cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **CONDICOES})
    return token, extra


def test_etapa_confirmar_tem_um_bloco_de_vistoria_por_moto_vinculada(cliente, base_contratos):
    _, extra = _com_vinculada(cliente, base_contratos)
    html = cliente.get(f"{BASE}?etapa=4").text
    assert "moto principal" in html and "(vinculada)" in html
    assert f'name="vinc1_moto" value="{extra}"' in html
    for nome in ("km", "nivel_combustivel", "avarias", "item_farol_dianteiro"):
        assert f'name="vinc1_{nome}"' in html
    assert 'id="vvinc1_-km"' in html and "A vistoria de todas as motos do contrato é obrigatória" in html


def test_etapa_confirmar_sem_vinculada_nao_muda(cliente, base_contratos):
    _preparar(cliente, base_contratos, ate=3)
    html = cliente.get(f"{BASE}?etapa=4").text
    assert "vinc1_" not in html and "moto principal" not in html and 'id="v-km"' in html


def test_criar_envia_a_vistoria_de_entrega_de_cada_vinculada(cliente, base_contratos, acoes_contratos_falsas):
    token, extra = _com_vinculada(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(), **_bloco_vinculada(1, extra)})
    assert resposta.status_code == 303 and len(acoes_contratos_falsas.chamadas) == 1
    (vistoria_extra,) = acoes_contratos_falsas.vistorias_vinculadas[0]
    assert vistoria_extra["moto_id"] == extra and vistoria_extra["km"] == 1000
    assert vistoria_extra["checklist"]["farol_dianteiro"] == "ok"


def test_criar_sem_a_vistoria_da_vinculada_volta_com_erro_e_nao_grava(cliente, base_contratos, acoes_contratos_falsas):
    token, extra = _com_vinculada(cliente, base_contratos)
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria()})
    assert acoes_contratos_falsas.chamadas == []
    assert resposta.status_code == 422 and "A lista de motos do contrato mudou" in resposta.text


def test_erro_na_vinculada_volta_com_o_texto_digitado_e_nao_grava(cliente, base_contratos, acoes_contratos_falsas):
    token, extra = _com_vinculada(cliente, base_contratos)
    ruim = _bloco_vinculada(1, extra, km="abc")
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(), **ruim})
    assert acoes_contratos_falsas.chamadas == [] and resposta.status_code == 422
    assert 'name="vinc1_km"' in resposta.text and 'value="abc"' in resposta.text
    assert 'name="km"' in resposta.text and 'value="5000"' in resposta.text  # o texto da principal também volta


def test_km_da_vinculada_menor_que_o_atual_e_recusado(cliente, base_contratos, acoes_contratos_falsas):
    token, extra = _com_vinculada(cliente, base_contratos)
    km_atual = base_contratos.moto_livre2["km_atual"]
    resposta = cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(), **_bloco_vinculada(1, extra, km=str(km_atual - 1))})
    assert acoes_contratos_falsas.chamadas == [] and resposta.status_code == 422


def test_texto_da_vinculada_sobrevive_a_voltar_e_reabrir(cliente, base_contratos):
    token, extra = _com_vinculada(cliente, base_contratos)
    cliente.post(f"{BASE}/criar", data={"csrf_token": token, **_vistoria(), **_bloco_vinculada(1, extra, km="1234", avarias="risco no tanque"), "acao": "voltar"})
    html = cliente.get(f"{BASE}?etapa=3").text  # volta para as condições
    cliente.post(f"{BASE}/condicoes", data={"csrf_token": token, **CONDICOES})
    html = cliente.get(f"{BASE}?etapa=4").text
    assert 'value="1234"' in html and "risco no tanque" in html
