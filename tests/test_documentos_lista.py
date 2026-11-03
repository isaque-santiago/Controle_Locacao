"""Regras puras da lista de documentos do frontend web."""

from datetime import date

from src.domain import documentos_lista as lista

HOJE = date(2026, 10, 8)


def _doc(vencimento, regularizado=False):
    return {"vencimento": vencimento, "regularizado": regularizado}


def _item(vencimento, placa="BRA2E19", regularizado=False, alerta=30):
    doc = _doc(vencimento, regularizado)
    return {"documento": doc, "placa": placa, **lista.classificar(doc, HOJE, alerta)}


def test_situacao_valida_cai_em_todos():
    assert lista.situacao_valida("vencido") == "vencido"
    assert lista.situacao_valida("x") == lista.TODOS and lista.situacao_valida(None) == lista.TODOS


def test_classifica_vencido_a_vencer_em_dia_e_regularizado():
    assert lista.classificar(_doc("2026-10-07"), HOJE, 30) == {"situacao": "vencido", "rotulo": "Vencido"}
    assert lista.classificar(_doc("2026-10-08"), HOJE, 30)["situacao"] == "a_vencer"
    assert lista.classificar(_doc("2026-11-07"), HOJE, 30)["situacao"] == "a_vencer"
    assert lista.classificar(_doc("2026-11-08"), HOJE, 30) == {"situacao": "em_dia", "rotulo": "Em dia"}
    assert lista.classificar(_doc("2020-01-01", True), HOJE, 30) == {"situacao": "em_dia", "rotulo": "Regularizado"}
    assert lista.classificar(_doc(date(2026, 10, 1)), HOJE, 30)["situacao"] == "vencido"  # aceita date


def test_busca_por_placa_com_ou_sem_hifen_e_filtro_por_situacao():
    itens = [_item("2026-10-01", "BRA2E19"), _item("2026-12-31", "QRS4T21")]
    assert len(lista.filtrar(itens, "todos", "bra-2e19")) == 1
    assert len(lista.filtrar(itens, "todos", "")) == 2
    assert [i["placa"] for i in lista.filtrar(itens, "em_dia", "")] == ["QRS4T21"]
    assert lista.filtrar(itens, "todos", "zzz") == []


def test_ordena_por_situacao_pendencia_e_vencimento_e_conta_sem_filtro():
    itens = [
        _item("2026-12-31", "A"), _item("2026-10-20", "B"), _item("2026-09-01", "C"),
        _item("2026-08-01", "D", regularizado=True), _item("2026-07-01", "E"),
    ]
    pagina, recorte, contagem = lista.montar_pagina(itens, "todos", "", 1, 10)
    assert [i["placa"] for i in pagina] == ["E", "C", "B", "A", "D"]  # vencidos, a vencer, em dia pendente antes do regularizado
    assert contagem == {"todos": 5, "vencido": 2, "a_vencer": 1, "em_dia": 2}
    pagina, recorte, contagem = lista.montar_pagina(itens, "vencido", "", 1, 1)
    assert [i["placa"] for i in pagina] == ["E"] and recorte.total == 2 and contagem["todos"] == 5
