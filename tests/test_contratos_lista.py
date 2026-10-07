"""Regras puras da lista de contratos (src/domain/contratos_lista.py)."""

from src.domain import contratos_lista as regras


def _item(status, inicio, nome="Ana", placa="BRA2E19"):
    return {"contrato": {"status": status, "data_inicio": inicio}, "cliente_nome": nome, "placa": placa}


def test_situacao_invalida_ou_ausente_volta_ao_padrao_ativo():
    assert regras.status_valido(None) == "ativo"
    assert regras.status_valido("xyz") == "ativo"
    assert regras.status_valido("todos") == "todos"
    assert regras.status_valido("encerrado") == "encerrado"


def test_aba_invalida_abre_cobrancas():
    assert regras.aba_valida("vistorias") == "vistorias"
    assert regras.aba_valida("portal") == "cobrancas"


def test_busca_por_nome_e_por_placa_com_ou_sem_hifen():
    itens = [_item("ativo", "2026-01-01", "Ana Souza", "BRA2E19"), _item("ativo", "2026-02-01", "Bia Lima", "QRS4T21")]
    assert [i["cliente_nome"] for i in regras.filtrar(itens, "todos", "souza")] == ["Ana Souza"]
    assert [i["cliente_nome"] for i in regras.filtrar(itens, "todos", "qrs-4t21")] == ["Bia Lima"]
    assert len(regras.filtrar(itens, "todos", "")) == 2
    assert regras.filtrar(itens, "todos", "---") == []  # só pontuação não casa com tudo


def test_montar_pagina_ordena_do_mais_recente_e_conta_sem_filtro():
    itens = [_item("ativo", "2026-01-01"), _item("encerrado", "2026-03-01"), _item("ativo", "2026-02-01")]
    pagina, recorte, contagem = regras.montar_pagina(itens, "ativo", "", 1, 10)
    assert [i["contrato"]["data_inicio"] for i in pagina] == ["2026-02-01", "2026-01-01"]
    assert recorte.total == 2 and contagem == {"ativo": 2, "encerrado": 1, "cancelado": 0}


def test_prazo_indeterminado_quando_nao_ha_data_final():
    assert regras.prazo_texto(None) is None
    assert regras.prazo_texto("2026-12-31T00:00:00") == "2026-12-31"
