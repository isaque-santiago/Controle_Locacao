"""Rota do Dashboard: acesso por papel e conteúdo mostrado."""

import re

from tests.web.conftest import entrar


def test_dashboard_exige_login(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/login")


def test_locatario_e_levado_ao_portal(cliente):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    resposta = cliente.get("/")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/portal"


def test_dashboard_mostra_indicadores_em_formato_brasileiro(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "<h1>Dashboard</h1>" in html
    assert "Terça-feira, 6 de outubro de 2026" in html
    assert "R$ 1.480" in html and "R$ 2.000" in html and "R$ 320" in html
    assert "60% de ocupação" in html
    assert "1 cliente atrasado" in html


def test_cartao_hoje_lista_atraso_e_vencimento_do_dia(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Atraso 5d" in html and "Vence hoje" in html
    assert "QRS-4T21" in html and "01/10/2026" in html and "R$ 320,00" in html
    assert 'aria-label="Registrar pagamento de Marcos Teles"' in html


def test_nomes_vindos_do_banco_sao_escapados(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "<b>Prado</b>" not in html
    assert "Joana &lt;b&gt;Prado&lt;/b&gt;" in html


def test_rosca_tem_texto_alternativo_e_um_arco_por_situacao(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    rosca = re.search(r'<div class="rosca" role="img" aria-label="([^"]+)">(.*?)</div>', html, re.S)
    assert rosca and "3 alugadas" in rosca.group(1)
    assert len(re.findall(r'<circle class="arco \w+"', rosca.group(2))) == 3
    assert "60%" in rosca.group(2)


def test_alertas_levam_para_a_area_certa(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'href="/manutencao" aria-label="Abrir: Manutenção vencida"' in html
    assert 'href="/documentos" aria-label="Abrir: Documento a vencer"' in html


def test_dashboard_sem_dados_mostra_estados_vazios(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    vazio = {**DADOS_PAINEL, "hoje": [], "alertas": [], "rosca": [], "atrasado": 0}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: vazio)
    entrar(cliente)
    html = cliente.get("/").text
    assert "Nenhuma cobrança vencendo hoje ou atrasada." in html
    assert "Nenhum alerta no momento." in html
    assert 'class="rosca"' not in html


def test_kpi_em_atraso_leva_as_cobrancas_atrasadas(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert '<a href="/cobrancas?aba=atrasadas">Em atraso</a>' in html
    assert cliente.get("/cobrancas?aba=atrasadas").status_code == 200


def test_indicadores_mostram_a_variacao_mensal_com_texto_e_tom(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'class="kpi-variacao bom"' in html
    assert "R$ 120 a mais (+9%) que no mesmo período de setembro." in html
    assert "R$ 40 a menos (−32%) que no mesmo período de setembro." in html
    assert '<span aria-hidden="true">↑</span>' in html  # a seta é decorativa; o texto diz "a mais"


def test_mes_da_secao_financeira_vem_da_url(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    pedidos = []
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: pedidos.append(k.get("mes")) or DADOS_PAINEL)
    entrar(cliente)
    assert cliente.get("/").status_code == 200
    assert cliente.get("/?mes=2026-08").status_code == 200
    assert pedidos == [None, "2026-08"]
    assert cliente.get("/?mes=" + "9" * 50).status_code == 200  # mês inválido: o serviço usa o mês atual


def test_secao_financeira_mostra_totais_do_mes_em_reais(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Financeiro · outubro de 2026" in html
    assert "R$ 3.445,50" in html and "R$ 5.161,20" in html and "R$ -1.715,70" in html
    assert "-50% de margem" in html
    assert "R$ 27.155,00" in html and "R$ 32.014,34" in html


def test_secao_financeira_lista_devedores_e_escapa_nomes(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Inadimplente" in html and "Em atraso" in html and "23 d" in html
    assert "POT-5B25" in html and "R$ 2.276,00" in html
    assert "<i>Souza</i>" not in html and "Ronildo &lt;i&gt;Souza&lt;/i&gt;" in html


def test_secao_financeira_tem_evolucao_e_seletor_de_mes(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "set./26" in html and "out./26" in html
    assert 'type="month" name="mes" value="2026-10" max="2026-10"' in html
    assert 'href="/?mes=2026-09"' in html
    assert "Mês seguinte" not in html and "Mês atual" not in html


def test_secao_financeira_de_mes_passado_oferece_voltar_ao_atual(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    passado = {**DADOS_PAINEL, "financeiro": {**DADOS_PAINEL["financeiro"], "e_mes_atual": False, "mes_seguinte": "2026-09"}}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: passado)
    entrar(cliente)
    html = cliente.get("/").text
    assert 'href="/?mes=2026-09" aria-label="Mês seguinte"' in html and ">Mês atual<" in html


def test_secao_financeira_sem_devedores_e_sem_receita(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    fin = DADOS_PAINEL["financeiro"]
    vazio = {**DADOS_PAINEL, "financeiro": {**fin, "atual": {**fin["atual"], "margem": None},
                                           "devedores": {**fin["devedores"], "ranking": [], "contratos_em_aberto": 0}}}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: vazio)
    entrar(cliente)
    html = cliente.get("/").text
    assert "Nenhum débito em atraso." in html and "sem receita no mês" in html
