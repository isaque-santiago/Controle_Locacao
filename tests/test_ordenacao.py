"""Ordenação de listas por coluna: interpretação do parâmetro, ordem com valores ausentes e os três domínios."""

from decimal import Decimal

from src.domain import clientes_lista, contratos_lista, motos_lista
from src.domain import ordenacao as o

MOTOS = [
    {"id": "1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG 160", "status": "alugada", "km_atual": 9000},
    {"id": "2", "placa": "QRS4T21", "marca": "Yamaha", "modelo": "Factor", "status": "disponivel", "km_atual": 120},
    {"id": "3", "placa": "ABC1D23", "marca": "Honda", "modelo": "Biz", "status": "inativa", "km_atual": 5000},
]


def test_interpretar_aceita_so_campos_permitidos():
    permitidas = ["km", "placa"]
    assert o.interpretar("km", permitidas) == ("km", False)
    assert o.interpretar("-km", permitidas) == ("km", True)
    assert o.interpretar("xpto", permitidas) == (None, False)
    assert o.interpretar("-", permitidas) == (None, False)
    assert o.interpretar(None, permitidas) == (None, False)


def test_proxima_cicla_crescente_decrescente_padrao():
    assert o.proxima(None, False, "km") == "km"
    assert o.proxima("placa", False, "km") == "km"
    assert o.proxima("km", False, "km") == "-km"
    assert o.proxima("km", True, "km") == ""


def test_ordenar_deixa_valores_ausentes_no_fim_nos_dois_sentidos():
    itens = [{"v": 2}, {"v": None}, {"v": 1}]
    assert [i["v"] for i in o.ordenar(itens, "v", False, {"v": lambda i: i["v"]})] == [1, 2, None]
    assert [i["v"] for i in o.ordenar(itens, "v", True, {"v": lambda i: i["v"]})] == [2, 1, None]
    assert o.ordenar(itens, None, False, {}) == itens


def test_cabecalhos_marcam_o_estado_e_o_proximo_clique():
    urls = o.cabecalhos({"Km": "km", "Placa": "placa"}, "km", False, lambda nova: f"/m?ordem={nova}")
    assert urls["Km"] == {"campo": "km", "url": "/m?ordem=-km", "estado": "ascending"}
    assert urls["Placa"]["estado"] == "none" and urls["Placa"]["url"] == "/m?ordem=placa"


def test_motos_por_km_e_por_locatario():
    assert [m["id"] for m in motos_lista.ordenar_motos(MOTOS, "km", False)] == ["2", "3", "1"]
    assert [m["id"] for m in motos_lista.ordenar_motos(MOTOS, "km", True)] == ["1", "3", "2"]
    # sem locatário vai para o fim; a alugada tem o único locatário
    assert [m["id"] for m in motos_lista.ordenar_motos(MOTOS, "locatario", False, {"1": "Ana"})][0] == "1"
    # situação segue a ordem dos chips (disponível, alugada, manutenção, inativa)
    assert [m["id"] for m in motos_lista.ordenar_motos(MOTOS, "situacao", False)] == ["2", "1", "3"]


def test_clientes_por_nome_e_cnh_sem_validade_no_fim():
    regs = [
        {"nome": "bruno", "status": "ativo", "cpf": "2", "cnh_validade": None},
        {"nome": "Ana", "status": "inativo", "cpf": "1", "cnh_validade": "2027-01-01"},
    ]
    assert [c["nome"] for c in clientes_lista.ordenar_clientes(regs, "nome", False)] == ["Ana", "bruno"]
    assert [c["nome"] for c in clientes_lista.ordenar_clientes(regs, "cnh", True)] == ["Ana", "bruno"]
    pagina, _, _ = clientes_lista.montar_pagina(regs, "todos", "", 1, 10, "situacao", True)
    assert [c["nome"] for c in pagina] == ["Ana", "bruno"]


def test_contratos_por_valor_usa_decimal_e_o_padrao_desempata():
    def item(cliente, inicio, valor):
        return {"contrato": {"status": "ativo", "data_inicio": inicio, "valor_periodo": valor}, "cliente_nome": cliente, "placa": ""}

    itens = [item("A", "2026-01-01", Decimal("100.00")), item("B", "2026-03-01", Decimal("100.00")), item("C", "2026-02-01", Decimal("90.00"))]
    pagina, _, _ = contratos_lista.montar_pagina(itens, "ativo", "", 1, 10, "valor", False)
    assert [i["cliente_nome"] for i in pagina] == ["C", "B", "A"]  # empate em 100,00: o mais recente primeiro
    pagina, _, _ = contratos_lista.montar_pagina(itens, "ativo", "", 1, 10)
    assert [i["cliente_nome"] for i in pagina] == ["B", "C", "A"]
