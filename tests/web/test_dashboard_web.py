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


def test_medidor_tem_texto_alternativo_e_um_segmento_por_moto_ativa(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    medidor = re.search(r'<div class="medidor" role="img" aria-label="([^"]+)">(.*?)</div>', html, re.S)
    assert medidor and "3 alugadas" in medidor.group(1)
    assert len(re.findall(r"<span", medidor.group(2))) == 5
    assert medidor.group(2).count('class="cheio"') == 3


def test_alertas_levam_para_a_area_certa(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'href="/manutencao" aria-label="Abrir: Manutenção vencida"' in html
    assert 'href="/documentos" aria-label="Abrir: Documento a vencer"' in html


def test_dashboard_sem_dados_mostra_estados_vazios(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    vazio = {**DADOS_PAINEL, "hoje": [], "alertas": [], "segmentos_medidor": [], "atrasado": 0}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: vazio)
    entrar(cliente)
    html = cliente.get("/").text
    assert "Nenhuma cobrança vencendo hoje ou atrasada." in html
    assert "Nenhum alerta no momento." in html
    assert 'class="medidor"' not in html
