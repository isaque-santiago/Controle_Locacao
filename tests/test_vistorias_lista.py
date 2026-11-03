"""Regras puras da lista de vistorias do frontend web."""

from src.domain import vistorias_lista as lista


def _item(tipo, data, cliente="Maria", placa="BRA2E19"):
    return {"vistoria": {"tipo": tipo, "data": data}, "cliente_nome": cliente, "placa": placa}


ITENS = [
    _item("entrega", "2026-08-01", "Maria Silva", "BRA2E19"),
    _item("devolucao", "2026-09-01", "João Souza", "QRS4T21"),
    _item("entrega", "2026-10-01", "Ana Lima", "ABC1D23"),
]


def test_tipo_valido_cai_em_todas():
    assert lista.tipo_valido("entrega") == "entrega"
    assert lista.tipo_valido("devolucao") == "devolucao"
    assert lista.tipo_valido("x") == lista.TODAS
    assert lista.tipo_valido(None) == lista.TODAS


def test_filtra_por_tipo_e_busca_por_cliente_ou_placa():
    assert len(lista.filtrar(ITENS, "entrega", "")) == 2
    assert [i["cliente_nome"] for i in lista.filtrar(ITENS, "todas", "joão")] == ["João Souza"]
    assert [i["cliente_nome"] for i in lista.filtrar(ITENS, "todas", "qrs-4t21")] == ["João Souza"]
    assert lista.filtrar(ITENS, "devolucao", "maria") == []
    assert lista.filtrar(ITENS, "todas", "-") == []  # só pontuação não casa com todas as placas


def test_pagina_ordena_pela_data_mais_recente_e_conta_sem_filtro():
    itens, recorte, contagem = lista.montar_pagina(ITENS, "devolucao", "", 1, 10)
    assert [i["cliente_nome"] for i in itens] == ["João Souza"]
    assert recorte.total == 1
    assert contagem == {"todas": 3, "entrega": 2, "devolucao": 1}
    itens, _, _ = lista.montar_pagina(ITENS, "todas", "", 1, 2)
    assert [i["cliente_nome"] for i in itens] == ["Ana Lima", "João Souza"]
    itens, recorte, _ = lista.montar_pagina(ITENS, "todas", "", 9, 2)  # página fora do intervalo é limitada
    assert recorte.pagina == 2 and [i["cliente_nome"] for i in itens] == ["Maria Silva"]
