"""Ficha da moto: acesso, abas carregadas pelo HTMX e conteúdo de cada aba."""

import re

from tests.web.conftest import entrar

MOTO = "00000000-0000-0000-0000-000000000001"
SEM_CONTRATO = "00000000-0000-0000-0000-000000000002"
PAINEL = {"HX-Request": "true", "HX-Target": "painel-aba"}


def test_ficha_exige_login_e_dono(cliente):
    assert cliente.get(f"/motos/{MOTO}").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(f"/motos/{MOTO}").status_code == 403


def test_moto_inexistente_ou_id_invalido_da_404(cliente):
    entrar(cliente)
    assert cliente.get("/motos/00000000-0000-0000-0000-0000000000ff").status_code == 404
    assert cliente.get("/motos/nao-e-um-uuid").status_code == 404
    assert cliente.get(f"/motos/{MOTO}/abas/invalida").status_code == 404
    assert cliente.get("/motos/nao-e-um-uuid/abas/resumo").status_code == 404


def test_cabecalho_da_ficha_mostra_placa_situacao_e_locatario(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}").text
    assert "<title>Moto ABC-1D01 · Controle de Locação</title>" in html
    assert len(re.findall(r"<h1[\s>]", html)) == 1
    assert "Honda CG 101, 2023, vermelha." in html
    assert "Locada para Joana &lt;b&gt;Prado&lt;/b&gt; desde 01/07/2026." in html
    assert "1.000 km" in html and "2023 / 2023" in html
    assert 'href="/motos"' in html and "Voltar para motos" in html


def test_ficha_abre_no_resumo_com_contrato_e_leituras(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}").text
    assert re.search(r'<button role="tab"[^>]*id="aba-resumo"[^>]*aria-selected="true"', html)
    assert 'id="painel-aba"' in html and 'aria-labelledby="aba-resumo"' in html
    assert "R$ 320,00" in html and "R$ 500,00" in html
    assert "03/10/2026" in html  # próxima cobrança = a mais antiga em aberto
    assert "1.000 km" in html and "01/09/2026 · manual" in html


def test_resumo_sem_contrato_ativo(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{SEM_CONTRATO}").text
    assert "Nenhum contrato ativo para esta moto." in html
    assert "Locada para" not in html


def test_aba_pedida_pela_url_abre_direto_nela(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}?aba=plano").text
    assert re.search(r'id="aba-plano"[^>]*aria-selected="true"', html)
    assert 'aria-labelledby="aba-plano"' in html and "Troca de óleo" in html
    assert "aria-selected=\"true\"" in html and html.count('aria-selected="true"') == 1


def test_aba_invalida_na_url_cai_no_resumo(cliente):
    entrar(cliente)
    assert 'aria-labelledby="aba-resumo"' in cliente.get(f"/motos/{MOTO}?aba=../../x").text


def test_abas_remotas_apontam_para_o_painel_e_para_a_url_da_pagina(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}").text
    assert len(re.findall(r'role="tab"', html)) == 6
    assert f'hx-get="/motos/{MOTO}/abas/historico"' in html
    assert f'hx-push-url="/motos/{MOTO}?aba=historico"' in html
    assert 'hx-target="#painel-aba" hx-swap="outerHTML"' in html
    assert html.count('tabindex="-1"') >= 5  # abas não selecionadas saem da ordem de Tab


def test_painel_devolvido_pelo_htmx_e_so_o_painel_da_aba(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}/abas/historico", headers=PAINEL).text
    assert "<html" not in html and 'aria-labelledby="aba-historico"' in html
    assert "28/08/2026" in html and "Preventiva" in html and "R$ 85,00" in html
    assert "Óleo &lt;i&gt;e filtro&lt;/i&gt;" in html and "<i>e filtro</i>" not in html


def test_aba_plano_mostra_intervalo_restante_e_situacao(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}/abas/plano", headers=PAINEL).text
    assert "3.000 km" in html and "3.500 km" in html and "2.500 km" in html
    assert 'class="selo atencao">Próxima' in html


def test_aba_documentos_marca_vencido(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}/abas/documentos", headers=PAINEL).text
    assert "CRLV" in html and "01/01/2020" in html and 'class="selo perigo">Vencido' in html


def test_aba_contratos_lista_atual_e_antigo_do_mais_recente_ao_mais_antigo(cliente):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}/abas/contratos", headers=PAINEL).text
    assert html.index("01/07/2026") < html.index("01/01/2026")
    assert "30/06/2026" in html and 'class="selo ok">Ativo' in html and 'class="selo neutro">Encerrado' in html


def test_aba_financeiro_mostra_resultado_e_custo_por_km(cliente, base_motos):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}/abas/financeiro", headers=PAINEL).text
    assert "R$ 1.200" in html and "R$ 1.115" in html and "R$ 0,09" in html
    base_motos.financeiro.clear()
    assert "Sem dados financeiros" in cliente.get(f"/motos/{MOTO}/abas/financeiro", headers=PAINEL).text


def test_abas_sem_registros_mostram_estado_vazio(cliente, base_motos):
    base_motos.manutencoes.clear()
    base_motos.documentos.clear()
    base_motos.plano_da_moto.clear()
    base_motos.leituras.clear()
    entrar(cliente)
    assert "Nenhuma manutenção registrada" in cliente.get(f"/motos/{MOTO}/abas/historico", headers=PAINEL).text
    assert "Nenhum documento cadastrado" in cliente.get(f"/motos/{MOTO}/abas/documentos", headers=PAINEL).text
    assert "Nenhum item no plano" in cliente.get(f"/motos/{MOTO}/abas/plano", headers=PAINEL).text
    assert "Nenhuma leitura registrada." in cliente.get(f"/motos/{MOTO}/abas/resumo", headers=PAINEL).text


def test_toda_aba_segue_as_regras_de_html(cliente):
    entrar(cliente)
    for aba in ("resumo", "plano", "historico", "documentos", "contratos", "financeiro"):
        for html in (
            cliente.get(f"/motos/{MOTO}?aba={aba}").text,
            cliente.get(f"/motos/{MOTO}/abas/{aba}", headers=PAINEL).text,
        ):
            assert not re.search(r"\sstyle\s*=|<style[\s>]|\son[a-z]+\s*=", html), aba
            assert len(re.findall(r"<h1[\s>]", html)) <= 1
