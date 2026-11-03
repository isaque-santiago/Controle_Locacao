"""Fase 3: Manutenção parte 1 (abas somente leitura)."""

from decimal import Decimal

from tests.web.conftest import entrar


def test_abre_em_alertas_com_resumo_contagens_e_ordem(cliente, base_manutencao):
    entrar(cliente)
    html = cliente.get("/manutencao").text
    assert "1 vencida(s) · 1 próxima(s)" in html
    for rotulo in ("Alertas", "Histórico", "Catálogo", "Todas <b>2", "Vencidas <b>1", "Próximas <b>1"):
        assert rotulo in html
    assert html.index("Filtro de ar") < html.index("Pneu &lt;traseiro&gt;")
    assert "-420 km" in html and "Em dia" not in html


def test_alertas_filtram_e_url_invalida_volta_ao_padrao(cliente, base_manutencao):
    entrar(cliente)
    proximas = cliente.get("/manutencao?situacao=proxima").text
    assert "Pneu &lt;traseiro&gt;" in proximas and "Filtro de ar" not in proximas
    invalida = cliente.get("/manutencao?situacao=xyz").text
    assert "Pneu &lt;traseiro&gt;" in invalida and "Filtro de ar" in invalida


def test_historico_filtra_busca_e_escapa_dados(cliente, base_manutencao):
    entrar(cliente)
    html = cliente.get("/manutencao?aba=historico&tipo=preventiva&q=central").text
    assert "Revisão &lt;geral&gt;" in html and "Buzina" not in html
    assert "BRA-2E19" in html and "R$ 95,00" in html and "Aberta" in html
    vazio = cliente.get("/manutencao?aba=historico&q=inexistente").text
    assert "Nenhuma manutenção encontrada" in vazio


def test_busca_htmx_usa_url_publica_e_restaura_pagina_inteira(cliente, base_manutencao):
    entrar(cliente)
    pagina = cliente.get("/manutencao?aba=historico").text
    assert 'hx-get="/manutencao"' in pagina and 'hx-push-url="true"' in pagina
    parcial = cliente.get(
        "/manutencao?aba=historico&q=central",
        headers={"HX-Request": "true", "HX-Target": "painel-aba"},
    ).text
    assert "<html" not in parcial and 'id="painel-aba"' in parcial
    restaurada = cliente.get(
        "/manutencao?aba=historico&q=central",
        headers={"HX-Request": "true", "HX-Target": "painel-aba", "HX-History-Restore-Request": "true"},
    ).text
    assert "<html" in restaurada


def test_historico_pagina_de_dez_preserva_filtros(cliente, base_manutencao):
    entrar(cliente)
    base_manutencao.manutencoes = [
        {"id": f"h{i}", "moto_id": "m1", "tipo": "preventiva", "status": "concluida",
         "data_entrada": f"2026-09-{(i % 27) + 1:02d}", "descricao": f"Revisão {i}", "oficina": "Central",
         "km": i * 100, "custo_total": Decimal("10")}
        for i in range(23)
    ]
    primeira = cliente.get("/manutencao?aba=historico&tipo=preventiva&q=central").text
    assert "Mostrando 1 a 10 de 23" in primeira
    assert 'hx-get="/manutencao/abas/historico?tipo=preventiva&amp;q=central&amp;pagina=2"' in primeira
    assert 'hx-push-url="/manutencao?aba=historico&amp;tipo=preventiva&amp;q=central&amp;pagina=2"' in primeira
    ultima = cliente.get("/manutencao/abas/historico?tipo=preventiva&q=central&pagina=99").text
    assert "Mostrando 21 a 23 de 23" in ultima


def test_catalogo_mostra_intervalos_faixa_e_inativos(cliente, base_manutencao):
    entrar(cliente)
    html = cliente.get("/manutencao?aba=catalogo").text
    assert "Kit de tração" in html and "5.000 km" in html and "3.000 km" in html and "Ativo" in html
    assert "Item antigo" in html and "90" in html and "Inativo" in html


def test_painel_parcial_troca_abas_sem_pagina_inteira(cliente, base_manutencao):
    entrar(cliente)
    html = cliente.get("/manutencao/abas/historico", headers={"HX-Request": "true"}).text
    assert "<html" not in html and 'hx-swap-oob="true"' in html and 'id="painel-aba"' in html
    assert 'id="aba-historico"' in html and 'aria-selected="true"' in html
    assert cliente.get("/manutencao/abas/inexistente").status_code == 404


def test_manutencao_exige_dono(cliente, base_manutencao):
    assert cliente.get("/manutencao").status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/manutencao").status_code == 403
    assert cliente.get("/manutencao/abas/alertas").status_code == 403
