"""Rota do Dashboard: três abas (Hoje, Dinheiro e Frota), acesso por papel, modos compacto e ocultar dados."""

import re
from decimal import Decimal

from tests.web.conftest import entrar, painel_falso

COBRANCA_A1 = "00000000-0000-0000-0000-0000000000a1"


def _com(monkeypatch, aba="hoje", **tudo):
    """Troca o que `carregar` devolve (a aba vem da URL; `tudo` vai para `painel_falso`)."""
    from src.domain import financeiro
    from src.web import dados_painel

    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: painel_falso(
        aba=financeiro.aba_do_painel(k.get("aba")), compacto=bool(k.get("compacto")), ocultar=bool(k.get("ocultar")), **tudo))


# ---------------------------------------------------------------------------------------------- acesso --


def test_dashboard_exige_login(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/login")


def test_locatario_e_levado_ao_portal(cliente):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    resposta = cliente.get("/")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/portal"


def test_so_o_simbolo_da_marca_e_link_para_o_dashboard(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'class="marca-simbolo" href="/"' in html
    assert '<a class="marca" href="/">' not in html


def test_aba_e_modos_da_url_chegam_ao_dashboard(cliente, monkeypatch):
    from src.web import dados_painel

    pedidos = []
    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: pedidos.append(k) or painel_falso())
    entrar(cliente)
    cliente.get("/")
    cliente.get("/?aba=dinheiro&mes=2026-08&compacto=1&ocultar=1")
    cliente.get("/?aba=frota&compacto=true&ocultar=0")
    assert pedidos[0] == {"mes": None, "compacto": False, "ocultar": False, "aba": None}
    assert pedidos[1] == {"mes": "2026-08", "compacto": True, "ocultar": True, "aba": "dinheiro"}
    assert pedidos[2]["aba"] == "frota" and pedidos[2]["compacto"] is False and pedidos[2]["ocultar"] is False
    assert cliente.get("/?mes=" + "9" * 50 + "&aba=" + "x" * 50).status_code == 200  # valor estranho: o serviço usa o padrão


# ---------------------------------------------------------------------------------------------- abas e menu --


def test_tres_abas_com_a_atual_marcada_e_sem_javascript(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    nav = re.search(r'<nav class="abas dash" aria-label="Seções do Dashboard">(.*?)</nav>', html, re.S).group(1)
    assert re.findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', nav) == [
        ("/", ' aria-current="page"', "Hoje"), ("/?aba=dinheiro", "", "Dinheiro"), ("/?aba=frota", "", "Frota")]


def test_cada_aba_marca_a_sua_e_mantem_os_modos_nos_links(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=frota&compacto=1&ocultar=1").text
    assert '<a href="/?aba=frota&amp;compacto=1&amp;ocultar=1" aria-current="page">Frota</a>' in html
    assert '<a href="/?compacto=1&amp;ocultar=1">Hoje</a>' in html and '<a href="/?aba=dinheiro&amp;compacto=1&amp;ocultar=1">Dinheiro</a>' in html


def test_os_dois_botoes_grandes_do_cabecalho_viraram_um_menu_de_opcoes(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'aria-label="Opções do Dashboard"' in html and "<span>Opções</span>" in html
    assert 'class="chip" href="/?compacto=1">Modo compacto</a>' in html and 'class="chip" href="/?ocultar=1">Ocultar dados pessoais</a>' in html
    cabecalho = html.split('<header class="cabecalho">', 1)[1].split("</header>", 1)[0]
    assert 'class="btn" href="/?compacto=1"' not in cabecalho


def test_o_menu_de_opcoes_diz_o_que_esta_ligado(cliente):
    entrar(cliente)
    html = cliente.get("/?compacto=1&ocultar=1").text
    assert "Sair do modo compacto" in html and "Mostrar dados pessoais" in html


# --------------------------------------------------------------------------------------------- aba Hoje --


def test_hoje_mostra_os_quatro_indicadores_em_reais(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    for rotulo in ("A cobrar", "Em atraso", "Frota", "Caixa do mês"):
        assert rotulo in html
    # A cobrar: vencido + vence hoje (sem encargos)
    assert "R$ 2.670" in html and "R$ 280 vencem hoje · R$ 2.390 em atraso" in html
    assert "R$ 2.390" in html and "2 contratos · 1 inadimplente" in html and "+ R$ 248 de encargos" in html
    assert "60% ocupada" in html and "3 de 5 motos ativas alugadas" in html and "1 livres · 1 em manutenção" in html
    assert "R$ -3.451,93" in html and "inclui R$ 800 de investimento em veículos" in html


def test_indicadores_levam_ao_detalhe(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert '<a href="/cobrancas?aba=atrasadas">A cobrar</a>' in html and '<a href="/cobrancas?aba=atrasadas">Em atraso</a>' in html
    assert '<a href="/?aba=frota">Frota</a>' in html and '<a href="/?aba=dinheiro">Caixa do mês</a>' in html
    assert cliente.get("/cobrancas?aba=atrasadas").status_code == 200


def test_cobrar_agora_junta_vencido_e_vence_hoje_com_pagar_e_whatsapp(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Cobrar agora" in html and "Quem está devendo" not in html and 'id="t-hoje"' not in html
    assert "44 d" in html and "hoje" in html and "R$ 2.276,00" in html and "R$ 347,00" in html and "R$ 295,00" in html
    assert "Inadimplente" in html and "Em atraso" in html and "Vence hoje" in html
    assert "QRS-4T21" in html and "BRA-2E19" in html
    assert f'href="/cobrancas/{COBRANCA_A1}/pagar"' in html and 'aria-label="Registrar pagamento de Joana &lt;b&gt;Prado&lt;/b&gt;"' in html
    assert f'hx-get="/cobrancas/{COBRANCA_A1}/mensagem" hx-target="#dlg-form-conteudo"' in html and ">WhatsApp</a>" in html
    assert 'aria-label="Mensagem de cobrança para Joana &lt;b&gt;Prado&lt;/b&gt;"' in html


def test_nomes_do_banco_sao_escapados_em_cobrar_agora(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "<b>Prado</b>" not in html and "Joana &lt;b&gt;Prado&lt;/b&gt;" in html


def test_cobrar_agora_limitado_mostra_quantos_ha_e_o_link_para_ver_todos(cliente, monkeypatch):
    bloco = painel_falso()["hoje"]["cobranca"]
    _com(monkeypatch, ajustes={"hoje": {"cobranca": {**bloco, "total_linhas": 24}}})
    entrar(cliente)
    html = cliente.get("/").text
    assert "mostrando 3 de 24 contratos, do maior atraso para o menor" in html and "Ver todas as cobranças" in html
    assert 'href="/cobrancas?aba=atrasadas">Ver todas as cobranças' in html


def test_sem_nada_para_cobrar_mostra_estado_vazio(cliente, monkeypatch):
    bloco = painel_falso()["hoje"]["cobranca"]
    vazio = {**bloco, "linhas": [], "total_linhas": 0, "a_cobrar": Decimal("0"), "em_atraso": Decimal("0"), "vencem_hoje": Decimal("0"),
             "encargos": Decimal("0"), "contratos_em_atraso": 0, "contratos_inadimplentes": 0, "contratos_so_hoje": 0}
    _com(monkeypatch, ajustes={"hoje": {"cobranca": vazio, "atencao": []}})
    entrar(cliente)
    html = cliente.get("/").text
    assert "Nada para cobrar agora" in html and "Nada precisa de atenção agora." in html and "+ R$ 0 de encargos" not in html


def test_atencao_e_uma_lista_so_com_botao_abrir_so_onde_ha_tela(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert "Precisa de atenção" not in html and "Alertas e pendências" not in html and 'id="t-alertas"' not in html
    atencao = html.split('id="t-atencao"', 1)[1].split("</section>", 1)[0]
    assert 'href="/dividas" aria-label="Abrir: Parcela de dívida atrasada"' in atencao
    assert 'href="/manutencao" aria-label="Abrir: Manutenção vencida"' in atencao and 'href="/documentos" aria-label="Abrir: Documento a vencer"' in atencao
    # pendência de dinheiro sem tela própria: "!" no lugar do número e sem botão
    assert 'aria-hidden="true">!</span>' in atencao and "Despesa a repassar ao locatário" in atencao
    assert "Abrir: Despesa a repassar" not in atencao


def test_alertas_do_whatsapp_levam_para_mensagens_e_configuracoes(cliente, monkeypatch):
    from src.domain.painel import ItemAlerta

    alertas = [
        ItemAlerta(2, "Mensagens sem entrega", "Maria: Número de WhatsApp inválido. e mais 1", "atencao", "mensagens"),
        ItemAlerta(1, "WhatsApp em modo teste", "As mensagens vão só para o número de teste, não para os clientes.", "atencao", "configuracoes"),
    ]
    _com(monkeypatch, ajustes={"hoje": {"atencao": alertas}})
    entrar(cliente)
    html = cliente.get("/").text
    assert 'href="/mensagens?filtro=problemas" aria-label="Abrir: Mensagens sem entrega"' in html
    assert 'href="/configuracoes#cfg-whatsapp" aria-label="Abrir: WhatsApp em modo teste"' in html


def test_caixa_indisponivel_nao_esconde_o_resto_da_aba_hoje(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"hoje": {"caixa": None}})
    entrar(cliente)
    html = cliente.get("/").text
    assert "indisponível agora" in html and "Cobrar agora" in html and "R$ 2.670" in html


def test_aba_hoje_indisponivel_mostra_o_aviso_e_mantem_a_atencao(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"hoje": {"indisponivel": True}})
    entrar(cliente)
    resposta = cliente.get("/")
    html = resposta.text
    assert resposta.status_code == 200 and "Cobrança de hoje indisponível agora" in html
    assert "Cobrar agora" not in html and "Manutenção vencida" in html and "Dashboard" in html


# ------------------------------------------------------------------------------------------ aba Dinheiro --


def test_dinheiro_mostra_totais_do_mes_em_reais_e_a_receita_contra_o_previsto(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    assert "Dinheiro · outubro de 2026" in html
    assert "R$ 3.445,50" in html and "R$ 5.161,20" in html and "R$ -1.715,70" in html and "-50% de margem" in html
    assert "de R$ 15.650 previstos (22%) · esperado até hoje: 57%" in html and "Semana: R$ 3.245,50" in html
    assert "R$ 27.155,00" in html and "R$ 32.014,34" in html and 'href="/dividas"' in html
    assert "R$ -3.451,93" in html and "R$ 1.056,23" in html


def test_dinheiro_nao_repete_o_que_ficou_para_hoje_e_frota(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    for sumiu in ("Quem está devendo", "Resultado por veículo", "Alertas e pendências", "Encargos de atraso", "Inadimplentes", "A receber"):
        assert sumiu not in html, sumiu


def test_dinheiro_tem_evolucao_com_texto_alternativo_entradas_e_categorias(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    grafico = re.search(r'<svg class="grafico-colunas"[^>]*aria-label="([^"]+)">(.*?)</svg>', html, re.S)
    assert grafico and "tabela logo abaixo" in grafico.group(1) and "style=" not in grafico.group(0)
    assert len(re.findall(r'class="col-receita"', grafico.group(2))) == 2 and "set./26" in grafico.group(2)
    assert "Entradas por conta" in html and "Sem conta informada" in html and "R$ 2.180,00" in html
    assert "Despesas por categoria" in html and "Manutenção" in html and "R$ 3.735,00" in html and "R$ 3.874,00" in html
    assert 'class="dash-lateral dash-lateral--coluna"' in html  # entradas e categorias empilhadas ao lado do gráfico, não espremidas lado a lado


def test_seletor_de_mes_so_existe_na_aba_dinheiro_e_leva_a_aba_junto(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro&compacto=1").text
    assert 'type="month" name="mes" value="2026-10" max="2026-10"' in html
    assert 'type="hidden" name="aba" value="dinheiro"' in html and 'type="hidden" name="compacto" value="1"' in html
    assert 'href="/?aba=dinheiro&amp;mes=2026-09&amp;compacto=1"' in html and "Mês seguinte" not in html and "Mês atual" not in html
    for outra in ("/", "/?aba=frota"):
        assert 'name="mes"' not in cliente.get(outra).text


def test_dinheiro_de_mes_passado_oferece_o_seguinte_e_voltar_ao_atual(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"dinheiro": {"e_mes_atual": False, "mes_seguinte": "2026-11", "mes_texto": "2026-09", "mes_anterior": "2026-08"}})
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    assert 'href="/?aba=dinheiro&amp;mes=2026-11" aria-label="Mês seguinte"' in html and ">Mês atual<" in html
    assert "Semana: R$" not in html and "dinheiro recebido" not in html


def test_dinheiro_indisponivel_mostra_o_aviso_e_mantem_o_seletor_de_mes(cliente, monkeypatch):
    chaves = ("mes", "mes_texto", "mes_rotulo", "mes_anterior", "mes_seguinte", "mes_maximo", "e_mes_atual")
    base = painel_falso("dinheiro")["dinheiro"]
    _com(monkeypatch, dinheiro={**{k: base[k] for k in chaves}, "indisponivel": True})
    entrar(cliente)
    resposta = cliente.get("/?aba=dinheiro")
    html = resposta.text
    assert resposta.status_code == 200 and "Dinheiro deste mês indisponível agora" in html and 'type="month" name="mes"' in html
    assert "Receita mensal estimada" not in html and "Últimos 6 meses" not in html


# -------------------------------------------------------------------------------------------- aba Frota --


def test_frota_mostra_ocupacao_manutencao_e_veiculos(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    assert "5 motos" in html and "60%" in html and "3 alugadas de 5 ativas" in html and "1 livres" in html
    assert "1 moto" in html and "1 ordem concluída no mês" in html and 'href="/manutencao"' in html
    assert "Gasto com manutenção no mês" in html and "R$ 85" in html and "igual à categoria Manutenção em Dinheiro" in html
    assert "Resultado por veículo" in html and "POU-7015" in html and "R$ 7.300,00" in html and "R$ -120,00" in html


def test_frota_tem_barra_segmentada_com_texto_alternativo_um_trecho_por_situacao_e_a_base_da_conta(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    barra = re.search(r'<svg class="barra-seg" [^>]*aria-label="([^"]+)">(.*?)</svg>', html, re.S)
    assert barra and "3 alugadas" in barra.group(1) and 'class="rosca"' not in html
    assert re.findall(r'class="seg (\w+)"', barra.group(2)) == ["cheio", "oficina", "livre"] and "60%" in html and "style=" not in barra.group(0)
    assert "Ocupação = alugadas ÷ motos ativas (5). Motos inativas não entram na conta." in html


def test_frota_escapa_o_locatario_e_recolhe_o_que_passa_de_cinco(cliente, monkeypatch):
    base = painel_falso("frota")["frota"]["veiculos"][0]
    veiculos = [{**base, "moto_id": f"m{i}", "placa": f"AAA{i}B{i:02d}", "locatario": "JOSE <u>HENRIQUE</u>", "resultado": Decimal(100 - i)} for i in range(8)]
    _com(monkeypatch, ajustes={"frota": {"veiculos": veiculos}})
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    assert "<u>HENRIQUE</u>" not in html and "JOSE &lt;u&gt;HENRIQUE&lt;/u&gt;" in html
    assert "Mostrar os outros 3 veículos" in html and '<details class="ver-mais">' in html


def test_frota_mostra_o_lancado_em_ordens_em_andamento(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"frota": {"manutencao_aberta": {"quantidade": 2, "total": Decimal("340.00")}}})
    entrar(cliente)
    assert "+ R$ 340 lançados em 2 ordens em andamento" in cliente.get("/?aba=frota").text
    _com(monkeypatch)
    assert "em andamento" not in cliente.get("/?aba=frota").text.split("Gasto com manutenção no mês", 1)[1].split("</dl>", 1)[0]


def test_frota_sem_a_leitura_do_dinheiro_mostra_traco_e_aviso_no_ranking(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"frota": {"indisponivel": True, "veiculos": []}})
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    assert "indisponível agora" in html and "Resultado por veículo indisponível agora" in html and "Ocupação da frota" in html


# ----------------------------------------------------------------------------------------- modos --


def test_ocultar_dados_pessoais_troca_valores_nomes_e_placas_em_todas_as_abas(cliente):
    entrar(cliente)
    segredos = {
        "/": ("R$ 2.670", "R$ 2.390", "R$ 2.276,00", "R$ -3.451,93", "Joana", "Marcos Teles", "QRS-4T21", "BRA-2E19", "R$ 1.000,00 em atraso", "R$ 40,00"),
        "/?aba=dinheiro": ("R$ 3.445,50", "R$ 2.180,00", "R$ 32.014,34", "R$ 27.155,00", "Luiza", "R$ 3.735,00"),
        "/?aba=frota": ("R$ 7.300,00", "JOSE", "POU-7015", "R$ 85"),
    }
    for caminho, lista in segredos.items():
        html = cliente.get(caminho + ("&" if "?" in caminho else "?") + "ocultar=1").text
        for segredo in lista:
            assert segredo not in html, (caminho, segredo)
        assert "R$ ••••" in html


def test_ocultar_esconde_os_graficos_e_as_barras_cujas_proporcoes_revelariam_valores(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro&ocultar=1").text
    assert "grafico-colunas" not in html and 'class="barra"' not in html and 'class="bullet"' not in html
    assert 'type="hidden" name="ocultar" value="1"' in html and "Mostrar dados pessoais" in html


def test_modo_compacto_da_hoje_mostra_so_indicadores_e_atencao(cliente):
    entrar(cliente)
    html = cliente.get("/?compacto=1").text
    assert "Sair do modo compacto" in html and "Cobrar agora" not in html
    assert "Atenção" in html and "A cobrar" in html and "Caixa do mês" in html


def test_modo_compacto_das_outras_abas_mostra_so_os_indicadores(cliente):
    entrar(cliente)
    dinheiro = cliente.get("/?aba=dinheiro&compacto=1").text
    assert "Receita mensal estimada" in dinheiro and "Últimos 6 meses" not in dinheiro and "Entradas por conta" not in dinheiro
    frota = cliente.get("/?aba=frota&compacto=1").text
    assert "Gasto com manutenção no mês" in frota and "Ocupação da frota" not in frota and "Resultado por veículo" not in frota


# ------------------------------------------------------------------------ Fase 2: contexto nos cartões --


def test_em_atraso_mostra_a_barra_e_a_legenda_das_faixas(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    barra = re.search(r'<svg class="barra-seg" [^>]*aria-label="(Atraso por faixa[^"]+)">(.*?)</svg>', html, re.S)
    assert barra and "7 a 14 dias" in barra.group(1) and re.findall(r'class="seg (f\d)"', barra.group(2)) == ["f2", "f4"]
    legenda = html.split('class="faixas-legenda"', 1)[1].split("</ul>", 1)[0]
    for texto in ("1 a 6 dias", "7 a 14 dias", "15 a 30 dias", "31 dias ou mais", "R$ 2.100,00", "R$ 290,00", "(1)", "(0)"):
        assert texto in legenda


def test_sem_nada_em_atraso_nao_desenha_a_barra(cliente, monkeypatch):
    bloco = painel_falso()["hoje"]["cobranca"]
    _com(monkeypatch, ajustes={"hoje": {"cobranca": {**bloco, "em_atraso": Decimal("0"), "linhas": [], "total_linhas": 0}}})
    entrar(cliente)
    assert "faixas-legenda" not in cliente.get("/").text


def test_frota_na_aba_hoje_tem_barra_e_o_caixa_tem_sparkline_com_texto_alternativo(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    assert 'aria-label="Frota de 5 motos: 3 alugadas, 1 disponíveis, 1 em manutenção, 0 inativas"' in html
    spark = re.search(r'<svg class="spark" [^>]*aria-label="([^"]+)">(.*?)</svg>', html, re.S)
    assert spark and "Caixa dos últimos 6 meses, de R$ -450,00 a R$ -3.451,93" in spark.group(1)
    assert 'points="3.0,21.0 60.0,12.0 117.0,3.0"' in spark.group(2) and "style=" not in spark.group(0)


def test_caixa_sem_serie_nao_desenha_sparkline(cliente, monkeypatch):
    caixa = painel_falso()["hoje"]["caixa"]
    _com(monkeypatch, ajustes={"hoje": {"caixa": {**caixa, "serie": None}}})
    entrar(cliente)
    assert 'class="spark"' not in cliente.get("/").text


def test_receita_tem_bullet_com_a_marca_do_esperado_ate_hoje(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    bullet = re.search(r'<svg class="bullet" [^>]*aria-label="([^"]+)">(.*?)</svg>', html, re.S)
    assert bullet and "22% do previsto; esperado até hoje: 57%" in bullet.group(1)
    assert 'class="bullet-valor" y="4" width="22"' in bullet.group(2) and 'class="bullet-marca" x1="57"' in bullet.group(2)


def test_mes_corrente_mostra_o_mes_anterior_e_nao_uma_variacao_injusta(cliente, monkeypatch):
    anterior = {**painel_falso("dinheiro")["dinheiro"]["atual"], "receita": Decimal("5500.40")}
    _com(monkeypatch, ajustes={"dinheiro": {"anterior": anterior}})
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    assert "mês anterior: R$ 5.500,40" in html and "kpi-variacao" not in html


def test_mes_fechado_mostra_variacao_colorida_pelo_resultado_em_texto(cliente, monkeypatch):
    v = {"receita": {"seta": "↑", "tom": "bom", "texto": "R$ 200 a mais (+20%) que no mesmo período de setembro."},
         "despesas": {"seta": "↑", "tom": "ruim", "texto": "R$ 100 a mais (+25%) que no mesmo período de setembro."},
         "resultado": None, "caixa": {"seta": "↓", "tom": "ruim", "texto": "R$ 150 a menos (−150%) que no mesmo período de setembro."}}
    _com(monkeypatch, ajustes={"dinheiro": {"variacoes": v, "e_mes_atual": False, "mes_seguinte": "2026-11"}})
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    assert 'class="kpi-variacao bom"' in html and 'class="kpi-variacao ruim"' in html
    assert "R$ 200 a mais (+20%)" in html and "R$ 150 a menos" in html
    assert "R$ 200 a mais" not in cliente.get("/?aba=dinheiro&ocultar=1").text


def test_ocultar_esconde_barras_bullet_e_sparkline_e_mascara_a_legenda_das_faixas(cliente):
    entrar(cliente)
    hoje = cliente.get("/?ocultar=1").text
    assert 'class="barra-seg"' not in hoje and 'class="spark"' not in hoje and "R$ 2.100,00" not in hoje and "R$ 290,00" not in hoje
    assert "faixas-legenda" in hoje and "31 dias ou mais" in hoje
    assert 'class="barra-seg"' not in cliente.get("/?aba=frota&ocultar=1").text


# ------------------------------------------------------------------------ Fase 3: o que faltava --


def test_proximos_dias_mostra_entra_sai_e_saldo_previsto(cliente):
    entrar(cliente)
    html = cliente.get("/").text
    caixa = html.split('id="t-proximos"', 1)[1].split("</section>", 1)[0]
    assert "Próximos 7 dias" in html and "R$ 1.250,00" in caixa and "(5 cobranças)" in caixa
    assert "R$ 1.536,23" in caixa and "(1 parcela de dívida)" in caixa and "R$ -286,23" in caixa and "Saldo previsto" in caixa


def test_sem_a_leitura_do_dinheiro_nao_ha_card_de_proximos_dias(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"hoje": {"proximos": None}})
    entrar(cliente)
    assert "Próximos 7 dias" not in cliente.get("/").text


def test_frota_tem_receita_por_moto_e_tempo_parado(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    assert "Receita por moto" in html and "R$ 689,10" in html and "receita do mês ÷ 5 motos ativas" in html
    assert "Tempo parado no mês" in html and "8.0%" in html and "12 dias de moto na oficina" in html


def test_tempo_parado_acima_de_5_por_cento_pede_atencao(cliente, monkeypatch):
    def classe_do_cartao(html):
        return re.search(r'<div class="(kpi[^"]*)"><dt>Tempo parado no mês', html).group(1)

    entrar(cliente)
    assert "atencao" in classe_do_cartao(cliente.get("/?aba=frota").text)  # 8,0% na fixture
    _com(monkeypatch, ajustes={"frota": {"tempo_parado": {"dias": 1, "percentual": Decimal("2.0")}}})
    assert "atencao" not in classe_do_cartao(cliente.get("/?aba=frota").text)


def test_motos_paradas_lista_motivo_desde_e_dias(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    paradas = html.split('id="t-paradas"', 1)[1].split("</section>", 1)[0]
    assert "OSL-8828" in paradas and "Em manutenção" in paradas and "28/09/2026" in paradas and "8 dias" in paradas
    assert "PMP-2B63" in paradas and "Disponível" in paradas and "sem contrato anterior" in paradas


def test_sem_motos_paradas_diz_que_todas_estao_alugadas(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"frota": {"paradas": {"total": 0, "linhas": []}}})
    entrar(cliente)
    assert "Nenhuma moto parada" in cliente.get("/?aba=frota").text


def test_ocultar_mascara_placas_e_valores_da_fase_3(cliente):
    entrar(cliente)
    hoje = cliente.get("/?ocultar=1").text
    assert "R$ 1.250,00" not in hoje and "R$ -286,23" not in hoje and "Próximos 7 dias" in hoje
    frota = cliente.get("/?aba=frota&ocultar=1").text
    assert "OSL-8828" not in frota and "R$ 689,10" not in frota and "Motos paradas" in frota


def test_modo_compacto_da_frota_esconde_a_lista_de_paradas(cliente):
    entrar(cliente)
    assert "Motos paradas" not in cliente.get("/?aba=frota&compacto=1").text


def test_moto_em_manutencao_sem_ordem_aberta_diz_isso_em_vez_de_contrato_anterior(cliente, monkeypatch):
    linha = {"moto_id": "m9", "placa": "PMZ8278", "motivo": "Em manutenção", "desde": None, "dias": None}
    _com(monkeypatch, ajustes={"frota": {"paradas": {"total": 1, "linhas": [linha]}}})
    entrar(cliente)
    paradas = cliente.get("/?aba=frota").text.split('id="t-paradas"', 1)[1].split("</section>", 1)[0]
    assert "sem ordem aberta" in paradas and "sem contrato anterior" not in paradas


# ------------------------------------------------------------------------ ajustes de layout (11/11/2026) --


def test_as_tres_abas_tem_a_mesma_largura_maxima_do_dashboard(cliente):
    entrar(cliente)
    for caminho in ("/", "/?aba=dinheiro", "/?aba=frota"):
        assert 'class="abas dash"' in cliente.get(caminho).text, caminho  # `main:has(.dash)` libera os 1600 px nas três


def test_dinheiro_destaca_a_receita_e_mostra_os_seis_meses_como_tabela(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=dinheiro").text
    assert '<dl class="grade kpis kpis-receita">' in html and 'class="cartao moto-lista-cards evolucao-lista"' in html


def test_frota_organiza_seis_indicadores_ocupacao_ao_lado_das_paradas_e_veiculos_embaixo(cliente):
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    assert '<dl class="grade kpis kpis-6">' in html and html.count('<div class="kpi') == 6
    linha = html.split('<div class="frota-linha', 1)[1].split("veiculos-lista", 1)[0]
    assert 'class="cartao ocupacao-card"' in linha and "paradas-lista" in linha
    assert 'class="ocupacao-tiles"' in html and html.count('class="tile-rotulo"') == 4
    assert html.index("t-veiculos") > html.index("t-paradas")  # resultado por veículo vem depois, em largura total


def test_frota_sem_a_leitura_do_dinheiro_volta_a_quatro_indicadores(cliente, monkeypatch):
    _com(monkeypatch, ajustes={"frota": {"indisponivel": True, "veiculos": []}})
    entrar(cliente)
    html = cliente.get("/?aba=frota").text
    assert "kpis-6" not in html and "Receita por moto" not in html and "ocupacao-card" in html
