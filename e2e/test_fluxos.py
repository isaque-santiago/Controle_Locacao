"""Os 10 fluxos de homologação (Etapa 9 do plano de UI/UX, absorvida pela Fase 4), no app novo.

O fluxo 1 (entrar e navegar) é coberto por test_login.py e test_paginas.py. Os fluxos 2 e 3 só leem. Os fluxos 4 a 10
GRAVAM no banco de DESENVOLVIMENTO (dados fictícios, marcados com "E2E"), por isso rodam uma vez por perfil (largura de
referência, tema claro) e só nos perfis Chromium (desktop e celular emulado). Cada fluxo desfaz o que faz sempre que o
app permite (encerra o contrato criado, restaura as configurações); o resto fica para recriar o banco de dev.

Um controle que não existe (lista vazia, rótulo alterado) vira achado INFO; um formulário recusado ou uma página que
quebra vira P0 e interrompe só aquele fluxo."""

import re
from typing import Callable

import pytest

from e2e.ajudas import aguardar_app, fechar_dialogo
from e2e.roteiro import (
    MARCA,
    Contexto,
    FormularioRecusado,
    grava_neste_cenario,
    hoje,
    imagem_de_teste,
)
from e2e.verificacoes import achados_bloqueantes

pytestmark = pytest.mark.autenticado

_PADRAO_KM = re.compile(r"(\d[\d.]*)\s*km", re.I)


def _numero(texto: str) -> int | None:
    achado = _PADRAO_KM.search(texto or "")
    return int(achado.group(1).replace(".", "")) if achado else None


def _km_do_campo(c: Contexto, campo: str, ajuda: str) -> int | None:
    """Km já preenchido no campo ou, se estiver vazio, o piso citado no texto de ajuda."""
    valor = c.page.locator(campo).input_value().strip().replace(".", "")
    if valor.isdigit():
        return int(valor)
    return _numero(c.page.locator(ajuda).inner_text()) if c.page.locator(ajuda).count() else None


# --------------------------------------------------------------------------
# Fluxos de leitura
# --------------------------------------------------------------------------
def fluxo_dashboard(c: Contexto) -> None:
    c.visitar("Dashboard")
    links = c.page.locator("section[aria-labelledby=t-alertas] a[href]").locator("visible=true")
    if not links.count():
        c.info("Dashboard", "Nenhum item de alerta com link para abrir.")
        return
    destino = links.first.get_attribute("href")
    links.first.click()
    aguardar_app(c.page)
    c.medir(f"Dashboard (alerta → {destino})", "dashboard-alerta")
    c.page.go_back()
    aguardar_app(c.page)


def _lista_busca_filtro_ficha(c: Contexto, titulo: str) -> None:
    c.visitar(titulo)
    busca = c.page.locator("#busca")
    busca.fill("a")
    c.page.wait_for_timeout(600)  # o filtro espera 300 ms depois de digitar
    aguardar_app(c.page)
    c.medir(f"{titulo} (busca)", f"{titulo}-busca")

    chips = c.page.locator("nav.chips a.chip").locator("visible=true")
    if chips.count() > 1:
        chips.nth(1).click()
        aguardar_app(c.page)
        c.medir(f"{titulo} (filtro)", f"{titulo}-filtro")
    proxima = c.page.locator("nav.paginacao a, nav.paginacao button").filter(has_text=re.compile("próxima", re.I))
    if proxima.count() and proxima.first.is_enabled():
        proxima.first.click()
        aguardar_app(c.page)
        c.medir(f"{titulo} (página 2)", f"{titulo}-pagina-2")

    if not c.clicar("link", re.compile(r"^Abrir (a )?ficha", re.I), titulo):
        return
    c.medir(f"{titulo} (ficha)", f"{titulo}-ficha")
    c.page.go_back()
    aguardar_app(c.page)
    if c.page.locator("#busca").count() and c.page.locator("#busca").input_value() != "a":
        c.reg("P1", "lista-perdeu-a-busca", titulo, "Ao voltar da ficha, a lista não manteve a busca digitada.")


def fluxo_buscar_e_abrir_fichas(c: Contexto) -> None:
    _lista_busca_filtro_ficha(c, "Motos")
    _lista_busca_filtro_ficha(c, "Clientes")


# --------------------------------------------------------------------------
# Fluxos que gravam
# --------------------------------------------------------------------------
def _escolher_na_tabela(c: Contexto, etapa: str, evitar: str | None) -> bool:
    """Seleciona a primeira linha elegível do assistente (linhas com `evitar` no texto são puladas)."""
    linhas = c.page.locator("tbody tr")
    if evitar:
        linhas = linhas.filter(has_not_text=re.compile(evitar))
    for i in range(linhas.count()):
        botao = linhas.nth(i).get_by_role("button", name=re.compile("^Selecionar$"))
        if botao.count() and botao.first.is_enabled():
            botao.first.click()
            aguardar_app(c.page)
            return True
    c.info("Contratos (assistente)", f"Nenhuma opção elegível na etapa {etapa}.")
    return False


def fluxo_contrato(c: Contexto) -> None:
    """Cria um contrato pelo assistente, abre a ficha e o encerra (devolve a moto e libera o cliente)."""
    c.visitar("Contratos")
    if not c.clicar("link", "Novo contrato", "Contratos"):
        return
    # Etapa 1: cliente
    c.medir("Contratos (assistente 1/4)", "contratos-assistente-1")
    if not _escolher_na_tabela(c, "1", r"Já aluga|não pode alugar") and not _escolher_na_tabela(c, "1", r"não pode alugar"):
        return  # sem cliente livre usa um que já aluga outra moto (o app permite; o aviso é só informativo)
    c.clicar("link", "Avançar", "Contratos (assistente 1/4)")
    # Etapa 2: moto
    c.medir("Contratos (assistente 2/4)", "contratos-assistente-2")
    if not _escolher_na_tabela(c, "2", None):
        return
    c.clicar("link", "Avançar", "Contratos (assistente 2/4)")
    # Etapa 3: condições
    km_inicial = _numero(c.page.locator(".contrato-layout").first.inner_text()) or 0
    c.preencher("#c-inicio", hoje().isoformat())
    c.preencher("#c-valor", "100,00")
    c.preencher("#c-caucao", "50,00")
    c.medir("Contratos (assistente 3/4)", "contratos-assistente-3")
    c.page.locator("#form-condicoes .rodape-acoes button[value=avancar]").click()
    aguardar_app(c.page)
    # Etapa 4: agenda e vistoria de entrega
    if not c.page.get_by_text("Prévia da agenda de cobranças").count():
        raise FormularioRecusado("Contratos (condições): " + " | ".join(c.erros_do_formulario())[:300])
    c.preencher("#v-km", str(_km_do_campo(c, "#v-km", "#v-km-ajuda") or km_inicial))
    c.preencher("#v-avarias", f"{MARCA}: vistoria de entrega do roteiro de homologação")
    c.medir("Contratos (assistente 4/4)", "contratos-assistente-4")
    avisos = c.enviar_formulario(c.page.get_by_role("button", name="Criar contrato", exact=True).last, "Criar contrato")
    if "/contratos/" not in c.page.url:
        raise FormularioRecusado(f"O contrato não abriu a ficha (avisos: {avisos})")
    c.medir("Contratos (ficha do contrato criado)", "contratos-ficha-criado")
    # Encerramento: devolve a moto e libera o cliente
    if not c.abrir_dialogo("button", "Encerrar contrato", "Contratos (ficha)", "contratos-encerrar", fechar=False):
        return
    c.preencher("#f-data-enc", hoje().isoformat())
    c.preencher("#v-km", str(_km_do_campo(c, "#v-km", "#v-km-ajuda") or km_inicial))
    c.page.locator("#f-confirmar-enc").check()
    c.esperar_previa()
    c.enviar_dialogo("Encerrar contrato", "contratos-encerrar-preenchido")
    c.medir("Contratos (depois de encerrar)", "contratos-encerrado")


def fluxo_pagamento(c: Contexto) -> None:
    """Pagamento parcial e, em seguida, a quitação da mesma cobrança."""
    c.visitar("Cobranças")
    botoes = c.page.locator("a, button").filter(has_text="Pagar").locator("visible=true")
    if not botoes.count():
        # Sem cobrança atrasada ou de hoje na aba atual: tenta a aba de atrasadas.
        c.clicar("tab", re.compile("atrasad", re.I), "Cobranças")
        botoes = c.page.locator("a, button").filter(has_text="Pagar").locator("visible=true")
    if not botoes.count():
        c.info("Cobranças", "Nenhuma cobrança com botão «Pagar» (nada a receber).")
        return
    nome = botoes.first.get_attribute("aria-label") or ""
    botoes.first.click()
    c.page.wait_for_selector("dialog[open] #f-principal")
    aguardar_app(c.page)
    c.preencher("#f-principal", "1,00")
    c.preencher("#f-extras", "0,00")
    avisos = c.enviar_dialogo("Pagamento parcial", "cobrancas-pagamento-parcial")
    c.reg("INFO", "aviso-de-sucesso", "Cobranças", "Aviso depois do pagamento parcial: " + " / ".join(avisos)[:160])
    c.medir("Cobranças (depois do pagamento parcial)", "cobrancas-parcial")
    # Quitação: a mesma cobrança continua em aberto com o restante
    restante = c.page.locator("a, button").filter(has_text="Pagar").locator("visible=true")
    alvo = c.page.locator(f'[aria-label="{nome}"]').locator("visible=true") if nome else restante
    if not alvo.count():
        c.info("Cobranças", "A cobrança paga em parte não voltou à lista para a quitação.")
        return
    alvo.first.click()
    c.page.wait_for_selector("dialog[open] #f-principal")
    aguardar_app(c.page)
    avisos = c.enviar_dialogo("Quitação", "cobrancas-pagamento-quitacao")
    c.reg("INFO", "aviso-de-sucesso", "Cobranças", "Aviso depois da quitação: " + " / ".join(avisos)[:160])
    c.medir("Cobranças (depois da quitação)", "cobrancas-quitada")


def fluxo_manutencao(c: Contexto) -> None:
    """Registra uma manutenção aberta e a conclui."""
    c.visitar("Manutenção")
    if not c.abrir_dialogo("link", "Registrar manutenção", "Manutenção", "manutencao-registrar", fechar=False) and not c.page.locator("dialog[open]").count():
        return
    if not c.page.locator("#f-moto").count():
        c.info("Manutenção", "Sem moto ativa para registrar manutenção.")
        fechar_dialogo(c.page)
        return
    moto = c.escolher("#f-moto", 0)
    c.esperar_previa()
    placa = moto.split("·")[0].strip()
    c.page.locator("#f-tipo").select_option("corretiva")
    c.page.locator("#f-status").select_option("aberta")
    c.esperar_previa()
    c.preencher("#f-entrada", hoje().isoformat())
    km = _km_do_campo(c, "#f-km", "#f-km-ajuda")
    if km is None:
        raise FormularioRecusado("Manutenção: não foi possível descobrir o km atual da moto")
    c.preencher("#f-km", str(km))
    c.preencher("#f-oficina", "Oficina E2E")
    c.preencher("#f-descricao", f"{MARCA}: manutenção do roteiro de homologação")
    c.enviar_dialogo("Registrar manutenção", "manutencao-registrar-preenchido")
    c.medir("Manutenção (depois de registrar)", "manutencao-registrada")
    # Conclusão
    candidatos = c.page.locator(f'a[aria-label*="Concluir manutenção da moto"][aria-label*="{placa}"], button[aria-label*="Concluir manutenção da moto"][aria-label*="{placa}"]').locator("visible=true")
    if not candidatos.count():
        c.info("Manutenção", f"Botão «Concluir» da moto {placa} não encontrado (a aba aberta pode ser outra).")
        return
    candidatos.first.click()
    c.page.wait_for_selector("dialog[open] #f-data-final")
    aguardar_app(c.page)
    c.preencher("#f-data-final", hoje().isoformat())
    c.preencher("#f-km-final", str(_km_do_campo(c, "#f-km-final", "#f-km-final-ajuda") or km))
    c.enviar_dialogo("Concluir manutenção", "manutencao-concluir")
    c.medir("Manutenção (depois de concluir)", "manutencao-concluida")


def fluxo_documento(c: Contexto) -> None:
    """Cadastra um documento com comprovante e o regulariza."""
    c.visitar("Documentos")
    if not c.abrir_dialogo("link", "Novo documento", "Documentos", "documentos-novo", fechar=False) and not c.page.locator("dialog[open]").count():
        return
    if not c.page.locator("#d-moto").count():
        c.info("Documentos", "Sem moto para cadastrar documento.")
        fechar_dialogo(c.page)
        return
    c.escolher("#d-moto", 0)
    c.preencher("#d-ano", str(hoje().year))
    c.preencher("#d-venc", hoje().replace(year=hoje().year + 1).isoformat())
    c.preencher("#d-valor", "10,00")
    c.preencher("#d-desc", f"{MARCA}: documento do roteiro de homologação")
    c.page.locator("#d-comprovante").set_input_files(imagem_de_teste("PNG"))
    c.enviar_dialogo("Novo documento", "documentos-novo-preenchido")
    c.medir("Documentos (depois de cadastrar)", "documentos-cadastrado")
    # Regularização do documento recém-criado
    linha = c.page.locator("tbody tr").filter(has_text=MARCA)
    if not linha.count():
        c.info("Documentos", "O documento criado não apareceu na página atual da lista (filtros ou paginação).")
        return
    linha.first.get_by_role("link", name=re.compile("^Marcar o documento")).click()
    c.page.wait_for_selector("dialog[open] #r-data")
    aguardar_app(c.page)
    c.preencher("#r-data", hoje().isoformat())
    c.page.locator("#r-comprovante").set_input_files(imagem_de_teste("PNG", cor=(20, 120, 200)))
    if c.page.locator("#r-proximo").count():
        c.page.locator("#r-proximo").uncheck()
    c.enviar_dialogo("Regularizar documento", "documentos-regularizar")
    c.medir("Documentos (depois de regularizar)", "documentos-regularizado")


def fluxo_vistoria(c: Contexto) -> None:
    """Registra uma vistoria com fotos em um contrato que ainda não a tem e abre a comparação."""
    c.visitar("Vistorias")
    if not c.abrir_dialogo("link", "Registrar vistoria", "Vistorias", "vistorias-registrar", fechar=False) and not c.page.locator("dialog[open]").count():
        return
    if c.page.locator("#v-contrato").count():
        c.escolher("#v-contrato", 0)
        c.page.locator("dialog[open] .dialogo-rodape button[type=submit]").click()
        c.page.wait_for_selector("dialog[open] #v-km")
        aguardar_app(c.page)
        km = _km_do_campo(c, "#v-km", "#v-km-ajuda")
        if km is None:
            raise FormularioRecusado("Vistorias: não foi possível descobrir o km mínimo")
        c.preencher("#v-data", hoje().isoformat())
        c.preencher("#v-km", str(km))
        c.preencher("#v-avarias", f"{MARCA}: vistoria do roteiro de homologação")
        c.page.locator("#v-fotos").set_input_files([imagem_de_teste("JPEG"), imagem_de_teste("PNG", cor=(20, 90, 160))])
        c.enviar_dialogo("Registrar vistoria", "vistorias-registrar-preenchido")
        c.medir("Vistorias (depois de registrar)", "vistorias-registrada")
    else:
        c.info("Vistorias", "Todos os contratos já têm as duas vistorias; só a comparação foi exercitada.")
        fechar_dialogo(c.page)
    if "/vistorias/contrato/" in c.page.url:
        c.medir("Vistorias (comparação)", "vistorias-comparacao")  # o registro já leva à comparação
    elif c.clicar("link", re.compile(r"^Comparar as vistorias", re.I), "Vistorias"):
        c.medir("Vistorias (comparação)", "vistorias-comparacao")


def fluxo_relatorios(c: Contexto, pasta_downloads) -> None:
    c.visitar("Relatórios")
    abas = c.page.get_by_role("tab").locator("visible=true")
    nomes = [abas.nth(i).inner_text().strip() for i in range(abas.count())]
    for nome in nomes:
        aba = c.page.get_by_role("tab", name=nome).first
        aba.click()
        aguardar_app(c.page)
        if aba.get_attribute("aria-selected") != "true":
            c.reg("P1", "aba-nao-selecionou", f"Relatórios · aba {nome}", "Depois do clique a aba não ficou selecionada.")
        c.medir(f"Relatórios · aba {nome}", f"relatorios-{nome}")
        if c.page.locator("#rel-de").count():
            c.page.locator("#rel-de").fill(hoje().replace(day=1).isoformat())
            c.page.locator("#rel-ate").fill(hoje().isoformat())
            c.page.get_by_role("button", name="Aplicar período").click()
            aguardar_app(c.page)
        for formato in ("Exportar CSV", "Exportar Excel"):
            link = c.page.get_by_role("link", name=formato).locator("visible=true")
            if not link.count():
                continue
            href = link.first.get_attribute("href")
            with c.page.expect_download() as baixando:
                link.first.click()
            c.reg("INFO", "exportacao", nome, f"{formato}: {href} → {baixando.value.suggested_filename}")
            destino = pasta_downloads / baixando.value.suggested_filename
            baixando.value.save_as(destino)
            conferir_arquivo(c, nome, destino)


def conferir_arquivo(c: Contexto, aba: str, caminho) -> None:
    """Abre o arquivo baixado: CSV com cabeçalho; Excel com planilha."""
    if caminho.suffix == ".csv":
        linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
        if not linhas or ";" not in linhas[0] and "," not in linhas[0]:
            c.reg("P0", "exportacao-invalida", aba, f"{caminho.name} sem cabeçalho.")
        # Dinheiro com duas casas (D3): nenhum valor monetário pode aparecer como 97,9
        if any(re.search(r"\b\d+,\d(?!\d)", linha) for linha in linhas[1:]):
            c.reg("P2", "csv-decimal-sem-zero", aba, f"{caminho.name} tem valor com uma só casa decimal.")
    else:
        from openpyxl import load_workbook

        try:
            livro = load_workbook(caminho)
        except Exception as erro:
            c.reg("P0", "exportacao-invalida", aba, f"{caminho.name} não abre no openpyxl: {type(erro).__name__}")
            return
        if not livro.worksheets or livro.worksheets[0].max_row < 1:
            c.reg("P0", "exportacao-invalida", aba, f"{caminho.name} sem planilha ou sem linhas.")


def fluxo_configuracoes(c: Contexto, pasta_downloads) -> None:
    """Altera um parâmetro, salva, restaura o valor original e baixa o backup."""
    c.visitar("Configurações")
    original = c.page.locator("#cfg-doc").input_value()
    novo = str(int(original or "30") + 1)
    c.preencher("#cfg-doc", novo)
    try:
        avisos = c.enviar_formulario(c.page.locator("button[form=form-config]").first, "Configurações (salvar)")
        c.reg("INFO", "aviso-de-sucesso", "Configurações", "Aviso depois de salvar: " + " / ".join(avisos)[:160])
        if c.page.locator("#cfg-doc").input_value() != novo:
            c.reg("P0", "configuracao-nao-salvou", "Configurações", "O valor salvo não voltou na página.")
    finally:
        c.preencher("#cfg-doc", original)
        c.enviar_formulario(c.page.locator("button[form=form-config]").first, "Configurações (restaurar)")
    with c.page.expect_download() as baixando:
        c.page.get_by_role("button", name=re.compile("Gerar e baixar backup")).click()
    arquivo = pasta_downloads / baixando.value.suggested_filename
    baixando.value.save_as(arquivo)
    import zipfile

    if not zipfile.is_zipfile(arquivo):
        c.reg("P0", "backup-invalido", "Configurações", f"{arquivo.name} não é um ZIP.")
    else:
        with zipfile.ZipFile(arquivo) as zip_:
            c.reg("INFO", "backup", "Configurações", f"{arquivo.name}: {len(zip_.namelist())} arquivos.")


# nome: (função, precisa de pasta de downloads, grava no banco)
FLUXOS: dict[str, tuple[Callable, bool, bool]] = {
    "02-dashboard-e-alertas": (fluxo_dashboard, False, False),
    "03-buscar-filtrar-abrir-moto-e-cliente": (fluxo_buscar_e_abrir_fichas, False, False),
    "04-criar-contrato": (fluxo_contrato, False, True),
    "05-registrar-pagamento": (fluxo_pagamento, False, True),
    "06-registrar-e-concluir-manutencao": (fluxo_manutencao, False, True),
    "07-cadastrar-e-regularizar-documento": (fluxo_documento, False, True),
    "08-registrar-abrir-e-comparar-vistorias": (fluxo_vistoria, False, True),
    "09-filtrar-e-exportar-relatorios": (fluxo_relatorios, True, False),
    "10-alterar-configuracoes-e-backup": (fluxo_configuracoes, True, True),
}


@pytest.mark.parametrize("nome_fluxo", list(FLUXOS))
def test_fluxo(nome_fluxo, pagina_logada, cenario, registrar, coletor, request, tmp_path):
    funcao, usa_downloads, grava = FLUXOS[nome_fluxo]
    if grava and not grava_neste_cenario(cenario):
        pytest.skip("fluxo que grava: roda uma vez por perfil Chromium (largura de referência, tema claro)")
    reg = registrar(cenario, fluxo=nome_fluxo)
    contexto = Contexto(pagina_logada, cenario, reg, request.config.getoption("--capturas"))
    try:
        if usa_downloads:
            funcao(contexto, tmp_path)
        else:
            funcao(contexto)
    except FormularioRecusado as erro:
        reg("P0", "formulario-recusado", nome_fluxo, str(erro))
    except Exception as erro:
        reg("P0", "fluxo-interrompido", nome_fluxo, f"{type(erro).__name__}: {str(erro)[:200]}")
    finally:
        fechar_dialogo(pagina_logada)

    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, fluxo=nome_fluxo)
        assert not bloqueantes, [f"{a.pagina}: {a.descricao}" for a in bloqueantes]

