"""Rota do Dashboard: acesso por papel e conteúdo mostrado."""

import re

from tests.web.conftest import DADOS_PAINEL, entrar


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


def test_cartao_hoje_limitado_mostra_link_para_ver_todas(cliente, monkeypatch):
    base = DADOS_PAINEL["hoje"][0]
    monkeypatch.setitem(DADOS_PAINEL, "hoje", [dict(base) for _ in range(7)])
    monkeypatch.setitem(DADOS_PAINEL, "hoje_total", 51)
    entrar(cliente)
    html = cliente.get("/").text
    assert "mostrando 7 de 51" in html
    assert "Ver todas as 51 cobranças" in html


def test_resultado_por_veiculo_recolhe_o_que_passa_de_cinco(cliente, monkeypatch):
    base = DADOS_PAINEL["financeiro"]["veiculos"][0]
    veiculos = [{**base, "placa": f"AAA{i}A00"} for i in range(8)]
    monkeypatch.setitem(DADOS_PAINEL, "financeiro", {**DADOS_PAINEL["financeiro"], "veiculos": veiculos})
    entrar(cliente)
    html = cliente.get("/").text
    assert "Mostrar os outros 3 veículos" in html
    assert '<details class="ver-mais">' in html


def test_ocupacao_explica_a_base_da_conta_e_legenda_bate_com_a_rosca(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "3 de 5 ativas" in html
    assert "Ocupação = alugadas ÷ motos ativas (5)" in html
    legenda = re.search(r'aria-label="Frota por situação">(.*?)</ul>', html, re.S).group(1)
    assert "60%" in legenda and "20%" in legenda
    assert "—" in legenda  # inativas ficam fora da conta


def test_recebido_mostra_barra_de_progresso_e_variacao_neutra(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'role="progressbar"' in html and 'aria-valuenow="74"' in html
    assert '<rect class="kpi-barra-cheia" width="74"' in html
    assert "kpi-variacao bom" not in html.split("Recebido no mês", 1)[1].split("Em atraso", 1)[0]


def test_ocultar_dados_pessoais_esconde_a_barra_de_progresso(cliente, monkeypatch):
    from src.web import dados_painel

    oculto = {**DADOS_PAINEL, "ocultar": True}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: oculto)
    entrar(cliente)
    html = cliente.get("/").text
    assert 'role="progressbar"' not in html


def test_manutencao_mostra_o_lancado_em_ordens_em_andamento(cliente, monkeypatch):
    from decimal import Decimal

    from src.web import dados_painel

    dados = {**DADOS_PAINEL, "manutencao_aberta": {"quantidade": 2, "total": Decimal("340.00")}}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: dados)
    entrar(cliente)
    html = cliente.get("/").text
    assert "Gasto com manutenção no mês" in html
    assert "+ R$ 340 lançados em 2 ordens em andamento" in html


def test_manutencao_sem_ordens_abertas_nao_mostra_linha_extra(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "em andamento" not in html.split("Gasto com manutenção no mês", 1)[1].split("</dl>", 1)[0]


def test_so_o_simbolo_da_marca_e_link_para_o_dashboard(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'class="marca-simbolo" href="/"' in html
    assert '<a class="marca" href="/">' not in html


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

    passado = {**DADOS_PAINEL, "financeiro": {**DADOS_PAINEL["financeiro"], "e_mes_atual": False, "mes_seguinte": "2026-09"},
               "links": {**DADOS_PAINEL["links"], "seguinte": "?mes=2026-09"}}
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


def test_grafico_de_colunas_tem_texto_alternativo_e_uma_coluna_por_mes(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    grafico = re.search(r'<svg class="grafico-colunas"[^>]*aria-label="([^"]+)">(.*?)</svg>', html, re.S)
    assert grafico and "tabela logo abaixo" in grafico.group(1)
    assert len(re.findall(r'class="col-receita"', grafico.group(2))) == 2
    assert len(re.findall(r'class="col-despesa"', grafico.group(2))) == 2
    assert "set./26" in grafico.group(2) and "out./26" in grafico.group(2)
    assert "style=" not in grafico.group(0)


def test_entradas_por_conta_e_despesas_por_categoria(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Entradas por conta" in html and "Sem conta informada" in html and "R$ 2.180,00" in html
    assert "Despesas por categoria" in html and "Manutenção" in html and "R$ 3.735,00" in html
    assert "R$ 3.874,00" in html


def test_resultado_por_veiculo_e_alertas_financeiros(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Resultado por veículo" in html and "POU-7015" in html and "R$ 7.300,00" in html and "R$ -120,00" in html
    assert "JOSE <u>HENRIQUE</u>" not in html and "JOSE &lt;u&gt;HENRIQUE&lt;/u&gt;" in html
    assert "Alertas e pendências" in html and "Contratos inadimplentes (15 dias ou mais)" in html
    assert "selo perigo" in html and "Crítico" in html and "selo info" in html


def test_receita_da_semana_so_aparece_no_mes_atual(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    entrar(cliente)
    assert "Semana: R$ 3.245,50" in cliente.get("/").text
    passado = {**DADOS_PAINEL, "financeiro": {**DADOS_PAINEL["financeiro"], "e_mes_atual": False, "mes_seguinte": "2026-10"}}
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: passado)
    assert "Semana: R$" not in cliente.get("/").text


def _com(monkeypatch, **mudancas):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: {**DADOS_PAINEL, **mudancas})


def test_ocultar_dados_pessoais_troca_valores_nomes_e_placas_no_proprio_html(cliente, monkeypatch):
    _com(monkeypatch, ocultar=True)
    entrar(cliente)
    html = cliente.get("/").text
    for segredo in ("R$ 3.445,50", "R$ 2.180,00", "R$ 7.300,00", "R$ 1.480", "R$ 320,00", "R$ 32.014,34",
                    "Joana", "Marcos Teles", "Ronildo", "JOSE", "Luiza", "POU-7015", "QRS-4T21", "POT-5B25"):
        assert segredo not in html, segredo
    assert "R$ ••••" in html and "••••••" in html
    assert "Mostrar dados pessoais" in html and 'type="hidden" name="ocultar" value="1"' in html
    assert "grafico-colunas" not in html and 'class="barra"' not in html
    assert "Atraso 5d" in html  # o que não identifica ninguém continua visível


def test_dados_visiveis_por_padrao_e_botao_para_ocultar(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Ocultar dados pessoais" in html and 'href="/?mes=2026-10&amp;ocultar=1"' in html
    assert "Modo compacto" in html and 'href="/?mes=2026-10"' in html


def test_modo_compacto_mostra_so_indicadores_e_alertas(cliente, monkeypatch):
    _com(monkeypatch, compacto=True)
    entrar(cliente)
    html = cliente.get("/").text
    assert "Sair do modo compacto" in html and 'type="hidden" name="compacto" value="1"' in html
    assert "Financeiro · outubro de 2026" in html and "Precisa de atenção" in html and "Alertas e pendências" in html
    for escondido in ("Ocupação da frota", "Últimos 6 meses", "Quem está devendo", "Entradas por conta",
                      "Despesas por categoria", "Resultado por veículo", 'id="t-hoje"'):
        assert escondido not in html, escondido


def test_modos_da_url_chegam_ao_dashboard(cliente, monkeypatch):
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    pedidos = []
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: pedidos.append(k) or DADOS_PAINEL)
    entrar(cliente)
    cliente.get("/?compacto=1&ocultar=1")
    cliente.get("/?compacto=true&ocultar=0")
    assert pedidos[0]["compacto"] is True and pedidos[0]["ocultar"] is True
    assert pedidos[1]["compacto"] is False and pedidos[1]["ocultar"] is False


def test_financeiro_indisponivel_mostra_aviso_e_o_resto_do_dashboard_continua(cliente, monkeypatch):
    from tests.web.conftest import DADOS_PAINEL

    fin = DADOS_PAINEL["financeiro"]
    indisponivel = {k: fin[k] for k in ("mes", "mes_texto", "mes_rotulo", "mes_anterior", "mes_seguinte", "mes_maximo", "e_mes_atual")}
    _com(monkeypatch, financeiro={**indisponivel, "indisponivel": True})
    entrar(cliente)
    resposta = cliente.get("/")
    html = resposta.text
    assert resposta.status_code == 200
    assert "Financeiro indisponível agora" in html and "Financeiro · outubro de 2026" in html
    assert 'type="month" name="mes"' in html
    assert "Receita mensal estimada" not in html and "Quem está devendo" not in html and "Resultado por veículo" not in html
    assert "Precisa de atenção" in html and "Ocupação da frota" in html and "Frota" in html


def test_alertas_do_whatsapp_levam_para_mensagens_e_configuracoes(cliente, monkeypatch):
    from src.domain.painel import ItemAlerta
    from src.web import dados_painel
    from tests.web.conftest import DADOS_PAINEL

    alertas = [
        ItemAlerta(2, "Mensagens sem entrega", "Maria: Número de WhatsApp inválido. e mais 1", "atencao", "mensagens"),
        ItemAlerta(1, "WhatsApp em modo teste", "As mensagens vão só para o número de teste, não para os clientes.", "atencao", "configuracoes"),
    ]
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: {**DADOS_PAINEL, "alertas": alertas})
    entrar(cliente)
    html = cliente.get("/").text
    assert 'href="/mensagens?filtro=problemas" aria-label="Abrir: Mensagens sem entrega"' in html
    assert 'href="/configuracoes#cfg-whatsapp" aria-label="Abrir: WhatsApp em modo teste"' in html
