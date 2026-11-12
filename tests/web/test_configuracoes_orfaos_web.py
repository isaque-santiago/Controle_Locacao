"""Configurações: procurar e apagar os arquivos órfãos do portal (botão com confirmação; só o dono)."""

from tests.web.conftest import csrf_da_sessao, entrar

ARQUIVOS = [
    {"bucket": "trocas_oleo", "caminho": "c1/painel-<b>.jpg", "tamanho": 2048, "criado_em": "2026-11-09T10:00:00+00:00"},
    {"bucket": "documentos", "caminho": "portal/c1/orfao.pdf", "tamanho": 3072, "criado_em": "2026-11-08T10:00:00+00:00"},
]


def test_pagina_oferece_so_o_botao_de_procurar(cliente, base_configuracoes):
    entrar(cliente)
    html = cliente.get("/configuracoes").text
    assert "Arquivos órfãos do portal" in html and 'action="/configuracoes/arquivos-orfaos/procurar"' in html
    assert "Procurar arquivos órfãos" in html and "/arquivos-orfaos/apagar" not in html  # apagar só depois de ver a lista
    assert "mais de 24 horas" in html and "vistorias" in html


def test_procurar_lista_os_arquivos_sem_apagar_nada(cliente, base_configuracoes):
    base_configuracoes.orfaos = ARQUIVOS
    entrar(cliente)
    resposta = cliente.post("/configuracoes/arquivos-orfaos/procurar", data={"csrf_token": csrf_da_sessao(cliente)})
    html = resposta.text
    assert resposta.status_code == 200 and "<html" in html and "2 arquivo(s) órfão(s)" in html and "5,0 KB" in html
    assert "Fotos de troca de óleo: 1" in html and "Comprovantes de documentos enviados pelo locatário: 1" in html
    assert "portal/c1/orfao.pdf" in html and "c1/painel-&lt;b&gt;.jpg" in html and "<b>.jpg" not in html  # caminho escapado
    assert 'action="/configuracoes/arquivos-orfaos/apagar"' in html and "Apagar 2 arquivo(s) órfão(s)" in html
    assert 'data-confirmar="Apagar 2 arquivo(s) órfão(s) do Storage? Não há como desfazer."' in html
    assert base_configuracoes.orfaos_apagados == 0


def test_procurar_sem_orfaos_diz_que_esta_limpo_e_nao_oferece_apagar(cliente, base_configuracoes):
    entrar(cliente)
    html = cliente.post("/configuracoes/arquivos-orfaos/procurar", data={"csrf_token": csrf_da_sessao(cliente)}).text
    assert "Nenhum arquivo órfão encontrado." in html and "/arquivos-orfaos/apagar" not in html


def test_erro_ao_procurar_aparece_no_cartao_sem_derrubar_a_pagina(cliente, base_configuracoes):
    base_configuracoes.erro_orfaos = ValueError("Informe pelo menos 1 hora de idade para os arquivos.")
    entrar(cliente)
    resposta = cliente.post("/configuracoes/arquivos-orfaos/procurar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 422 and "pelo menos 1 hora" in resposta.text and "Backup manual" in resposta.text
    base_configuracoes.erro_orfaos = RuntimeError("tabela inexistente")
    resposta = cliente.post("/configuracoes/arquivos-orfaos/procurar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code in (500, 503) and "tabela inexistente" not in resposta.text and "Backup manual" in resposta.text


def test_apagar_avisa_quantos_e_volta_para_o_cartao(cliente, base_configuracoes):
    base_configuracoes.orfaos = ARQUIVOS
    entrar(cliente)
    resposta = cliente.post("/configuracoes/arquivos-orfaos/apagar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 303 and resposta.headers["location"] == "/configuracoes#cfg-orfaos"
    assert base_configuracoes.orfaos_apagados == 1
    assert "2 arquivo(s) órfão(s) apagado(s) (5,0 KB)." in cliente.get("/configuracoes").text


def test_apagar_com_falha_parcial_vira_alerta(cliente, base_configuracoes):
    base_configuracoes.orfaos = ARQUIVOS
    base_configuracoes.falhas_ao_apagar = 1
    entrar(cliente)
    cliente.post("/configuracoes/arquivos-orfaos/apagar", data={"csrf_token": csrf_da_sessao(cliente)})
    html = cliente.get("/configuracoes").text
    assert "1 arquivo(s) órfão(s) apagado(s)" in html and "1 arquivo(s) não puderam ser apagados agora" in html


def test_erro_ao_apagar_mostra_a_mensagem_e_nao_apaga(cliente, base_configuracoes):
    base_configuracoes.erro_orfaos = RuntimeError("Storage fora do ar")
    entrar(cliente)
    resposta = cliente.post("/configuracoes/arquivos-orfaos/apagar", data={"csrf_token": csrf_da_sessao(cliente)})
    assert resposta.status_code == 303 and base_configuracoes.orfaos_apagados == 0
    assert "Storage fora do ar" not in cliente.get("/configuracoes").text


def test_apagar_nao_aceita_lista_vinda_do_navegador(cliente, base_configuracoes):
    """A rota ignora qualquer campo: o serviço recalcula a lista no banco (o fake não recebe argumento nenhum)."""
    entrar(cliente)
    cliente.post("/configuracoes/arquivos-orfaos/apagar", data={"csrf_token": csrf_da_sessao(cliente), "caminho": "vistorias/importante.jpg", "bucket": "vistorias"})
    assert base_configuracoes.orfaos_apagados == 1


def test_procurar_e_apagar_exigem_dono_e_csrf(cliente, base_configuracoes):
    for caminho in ("procurar", "apagar"):
        assert cliente.post(f"/configuracoes/arquivos-orfaos/{caminho}", data={}).status_code in (303, 401, 403)
    entrar(cliente)
    for caminho in ("procurar", "apagar"):
        assert cliente.post(f"/configuracoes/arquivos-orfaos/{caminho}", data={}).status_code in (400, 403)
    assert base_configuracoes.orfaos_apagados == 0
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.post("/configuracoes/arquivos-orfaos/apagar", data={}).status_code == 403
