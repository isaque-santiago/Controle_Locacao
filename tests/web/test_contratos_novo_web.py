"""Fase 3: assistente de novo contrato (quatro etapas) no app FastAPI."""

from src.domain.vistorias import CHECKLIST_PADRAO
from tests.web.conftest import csrf_da_sessao, entrar

BASE = "/contratos/novo"
CONDICOES = {"data_inicio": "2026-10-07", "indeterminado": "on", "periodicidade": "semanal",
             "valor_periodo": "320,00", "caucao_valor": "500,00", "data_fim_prevista": "2026-11-06", "acao": "avancar"}


def _vistoria(**extra):
    return {"km": "5000", "nivel_combustivel": "cheio", "adicionais": "", "avarias": "", "acao": "criar",
            **{f"item_{i}": "ok" for i in CHECKLIST_PADRAO}, **extra}


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
