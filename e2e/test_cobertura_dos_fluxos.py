"""Garante que todos os fluxos mínimos da Etapa 9 têm cenário de teste."""

from e2e.config import PAGINAS
from e2e.test_fluxos import FLUXOS

FLUXOS_MINIMOS = (
    "01-entrar-e-navegar",
    "02-dashboard-e-alertas",
    "03-buscar-filtrar-abrir-moto-e-cliente",
    "04-criar-contrato",
    "05-registrar-pagamento",
    "06-registrar-e-concluir-manutencao",
    "07-cadastrar-e-regularizar-documento",
    "08-registrar-abrir-e-comparar-vistorias",
    "09-filtrar-e-exportar-relatorios",
    "10-alterar-configuracoes-e-backup",
)


def test_todos_os_fluxos_minimos_tem_cenario():
    # O fluxo 1 é implementado por test_login.py + test_paginas.py.
    implementados = {"01-entrar-e-navegar", *FLUXOS}
    assert implementados == set(FLUXOS_MINIMOS)


def test_inventario_de_paginas_espelha_o_app():
    from src.web.navegacao import TODOS

    assert [(i.rotulo, i.caminho) for i in TODOS] == [(p.titulo, p.caminho) for p in PAGINAS]
