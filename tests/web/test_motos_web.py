"""Lista de motos: acesso, filtro, busca, paginação e troca parcial pelo HTMX."""

import re

from tests.web.conftest import _moto, entrar

HTMX = {"HX-Request": "true", "HX-Target": "resultado"}


def test_lista_exige_login(cliente):
    resposta = cliente.get("/motos")
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/login")


def test_locatario_nao_acessa_a_lista(cliente):
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get("/motos").status_code == 403


def test_lista_mostra_motos_com_dados_formatados(cliente):
    entrar(cliente)
    html = cliente.get("/motos").text
    assert "<h1>Motos</h1>" in html
    assert "3 motos cadastradas" in html
    assert "ABC1D01" not in html and "ABC-1D01" in html  # placa formatada
    assert "Honda CG 101" in html and "1.000" in html
    assert "vencida há 120 km" in html
    assert 'class="c-man text-perigo font-medium"' in html


def test_locatario_do_contrato_ativo_e_escapado(cliente):
    entrar(cliente)
    html = cliente.get("/motos").text
    assert "Joana &lt;b&gt;Prado&lt;/b&gt;" in html and "<b>Prado</b>" not in html
    assert "Sem locatário" in html


def test_chips_mostram_contagens_e_marcam_o_filtro_atual(cliente):
    entrar(cliente)
    html = cliente.get("/motos?situacao=alugada").text
    assert re.search(r'<a class="chip" href="/motos\?situacao=alugada"[^>]*aria-current="true">Alugada <b>1</b>', html)
    assert re.search(r'<a class="chip" href="/motos"[^>]*>Todas <b>3</b></a>', html)
    assert "Honda CG 101" in html and "Factor" not in html


def test_situacao_invalida_vira_todas(cliente):
    entrar(cliente)
    html = cliente.get("/motos?situacao=xpto").text
    assert "Factor" in html and "Honda CG 101" in html


def test_busca_por_placa_com_hifen_e_por_locatario(cliente):
    entrar(cliente)
    assert "Factor" in cliente.get("/motos?q=abc-2d02").text
    html = cliente.get("/motos?q=joana").text
    assert "Honda CG 101" in html and "Factor" not in html


def test_busca_sem_resultado_oferece_limpar_filtros(cliente):
    entrar(cliente)
    html = cliente.get("/motos?q=nao-existe").text
    assert "Nenhuma moto encontrada" in html
    assert 'href="/motos"' in html and "Limpar filtros" in html


def test_sem_motos_cadastradas_mostra_estado_vazio(cliente, base_motos):
    base_motos.motos.clear()
    entrar(cliente)
    html = cliente.get("/motos").text
    assert "Nenhuma moto cadastrada" in html and "<table" not in html


def test_termo_da_busca_e_escapado_no_campo(cliente):
    entrar(cliente)
    html = cliente.get('/motos?q="><script>alert(1)</script>').text
    assert "<script>alert(1)" not in html
    assert "&#34;&gt;&lt;script&gt;" in html


def test_paginacao_divide_a_lista_e_preserva_filtro_na_url(cliente, base_motos):
    base_motos.motos[:] = [_moto(i, "disponivel") for i in range(1, 26)]
    entrar(cliente)
    html = cliente.get("/motos").text
    assert "Mostrando 1 a 10 de 25" in html
    assert 'href="/motos?pagina=2"' in html
    pagina3 = cliente.get("/motos?pagina=3&situacao=disponivel").text
    assert "Mostrando 21 a 25 de 25" in pagina3
    assert 'href="/motos?situacao=disponivel&amp;pagina=2"' in pagina3
    assert 'rel="next"' not in pagina3 and 'href="/motos?situacao=disponivel&amp;pagina=4"' not in pagina3


def test_pagina_alem_do_fim_e_valor_invalido_nao_quebram(cliente, base_motos):
    base_motos.motos[:] = [_moto(i) for i in range(1, 13)]
    entrar(cliente)
    assert "Mostrando 11 a 12 de 12" in cliente.get("/motos?pagina=99").text
    assert "Mostrando 1 a 10 de 12" in cliente.get("/motos?pagina=abc").text
    assert "Mostrando 1 a 10 de 12" in cliente.get("/motos?por_pagina=7").text


def test_tamanho_da_pagina_e_escolhido_na_lista(cliente, base_motos):
    base_motos.motos[:] = [_moto(i) for i in range(1, 31)]
    entrar(cliente)
    html = cliente.get("/motos?por_pagina=25").text
    assert "Mostrando 1 a 25 de 30" in html
    assert re.search(r'<option value="25" selected>', html)
    assert 'href="/motos?por_pagina=25&amp;pagina=2"' in html


def test_htmx_devolve_so_o_resultado(cliente):
    entrar(cliente)
    html = cliente.get("/motos?situacao=alugada", headers=HTMX).text
    assert "<html" not in html and 'class="chips"' in html and "Honda CG 101" in html


def test_restaurar_o_historico_do_htmx_devolve_a_pagina_inteira(cliente):
    entrar(cliente)
    html = cliente.get("/motos", headers={**HTMX, "HX-History-Restore-Request": "true"}).text
    assert "<html" in html


def test_lista_nao_usa_estilo_nem_script_inline(cliente):
    entrar(cliente)
    html = cliente.get("/motos").text
    assert not re.search(r"\sstyle\s*=|<style[\s>]|\son[a-z]+\s*=", html)
    ids_com_rotulo = set(re.findall(r"<label[^>]*\sfor=\"([^\"]+)\"", html))
    for campo in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
        if 'type="hidden"' not in campo:
            assert re.search(r'\sid="([^"]+)"', campo).group(1) in ids_com_rotulo
