"""Regras puras de paginação e de filtros ativos das listas (Plano de melhorias, Etapa 3)."""

import pytest

from src.domain.paginacao import OPCOES_POR_PAGINA, calcular_pagina, filtros_ativos


def test_primeira_pagina_de_lista_com_varias_paginas():
    p = calcular_pagina(23, 1, 10)
    assert (p.pagina, p.total_paginas, p.inicio, p.fim) == (1, 3, 0, 10)
    assert not p.tem_anterior and p.tem_proxima


def test_ultima_pagina_parcial():
    p = calcular_pagina(23, 3, 10)
    assert (p.inicio, p.fim) == (20, 23)
    assert p.tem_anterior and not p.tem_proxima


def test_total_multiplo_do_tamanho_da_pagina_nao_cria_pagina_vazia():
    assert calcular_pagina(20, 2, 10).total_paginas == 2
    assert calcular_pagina(20, 2, 10).fim == 20


def test_pagina_alem_do_fim_volta_para_a_ultima():
    # o filtro encolheu a lista depois de a página 5 ter sido aberta
    p = calcular_pagina(12, 5, 10)
    assert (p.pagina, p.total_paginas, p.inicio, p.fim) == (2, 2, 10, 12)


@pytest.mark.parametrize("pagina", [0, -3, None])
def test_pagina_invalida_vira_a_primeira(pagina):
    assert calcular_pagina(50, pagina, 10).pagina == 1


def test_lista_vazia_tem_uma_pagina_e_nenhum_item():
    p = calcular_pagina(0, 1, 10)
    assert (p.pagina, p.total_paginas, p.inicio, p.fim) == (1, 1, 0, 0)
    assert p.resumo() == "Nenhum resultado"


def test_por_pagina_invalido_e_limitado_a_um():
    assert calcular_pagina(5, 1, 0).por_pagina == 1


def test_resumo_da_pagina():
    assert calcular_pagina(23, 2, 10).resumo() == "Mostrando 11 a 20 de 23 · página 2 de 3"
    assert calcular_pagina(23, 3, 10).resumo() == "Mostrando 21 a 23 de 23 · página 3 de 3"


def test_opcoes_de_itens_por_pagina_comecam_no_padrao():
    assert OPCOES_POR_PAGINA == (10, 25, 50)


def test_filtros_ativos_ignora_o_estado_inicial():
    assert filtros_ativos("todos", "todos", "") == []
    assert filtros_ativos("todos", "todos", "   ") == []


def test_filtros_ativos_reconhece_filtro_e_busca():
    assert filtros_ativos("vencido", "todos", "") == ["filtro"]
    assert filtros_ativos("todos", "todos", "abc") == ["busca"]
    assert filtros_ativos("vencido", "todos", "abc") == ["filtro", "busca"]


def test_padrao_diferente_de_todos_conta_como_inicial():
    # Contratos abre em "ativo": esse é o estado inicial, "Todos" é que é um filtro escolhido
    assert filtros_ativos("ativo", "ativo", "") == []
    assert filtros_ativos("todos", "ativo", "") == ["filtro"]
