"""Busca global: veículos (placa/modelo), clientes (nome/CPF) e contratos num só termo."""

from src.domain import busca_global

MOTOS = [
    {"id": "m1", "placa": "ABC1D23", "marca": "Honda", "modelo": "CG 160", "status": "alugada"},
    {"id": "m2", "placa": "XYZ9K88", "marca": "Yamaha", "modelo": "Factor", "status": "disponivel"},
    {"id": "m3", "placa": "ABC1D99", "marca": "Honda", "modelo": "Biz", "status": "inativa", "arquivado_em": "2026-01-01"},
]
CLIENTES = [
    {"id": "c1", "nome": "Joana Prado", "cpf": "123.456.789-09"},
    {"id": "c2", "nome": "Carlos Souza", "cpf": "98765432100"},
    {"id": "c3", "nome": "Joana Antiga", "cpf": "111.222.333-44", "arquivado_em": "2026-01-01"},
]
CONTRATOS = [
    {"id": "k1", "cliente_id": "c1", "moto_id": "m1", "status": "encerrado", "data_inicio": "2026-01-10"},
    {"id": "k2", "cliente_id": "c1", "moto_id": "m1", "status": "ativo", "data_inicio": "2026-05-10"},
    {"id": "k3", "cliente_id": "c2", "moto_id": "m2", "status": "ativo", "data_inicio": "2026-06-01"},
]


def test_termo_curto_ou_vazio_nao_busca():
    for termo in (None, "", " ", "a"):
        assert busca_global.buscar(termo, MOTOS, CLIENTES, CONTRATOS)["total"] == 0


def test_placa_com_ou_sem_hifen_e_modelo():
    assert [m["id"] for m in busca_global.buscar("abc-1d23", MOTOS, CLIENTES, CONTRATOS)["veiculos"]] == ["m1"]
    assert [m["id"] for m in busca_global.buscar("abc1d23", MOTOS, CLIENTES, CONTRATOS)["veiculos"]] == ["m1"]
    assert [m["id"] for m in busca_global.buscar("factor", MOTOS, CLIENTES, CONTRATOS)["veiculos"]] == ["m2"]


def test_cliente_por_nome_e_por_cpf_com_ou_sem_pontuacao():
    assert [c["id"] for c in busca_global.buscar("joana", MOTOS, CLIENTES, CONTRATOS)["clientes"]] == ["c1"]
    assert [c["id"] for c in busca_global.buscar("123.456", MOTOS, CLIENTES, CONTRATOS)["clientes"]] == ["c1"]
    assert [c["id"] for c in busca_global.buscar("98765", MOTOS, CLIENTES, CONTRATOS)["clientes"]] == ["c2"]


def test_arquivados_ficam_de_fora():
    r = busca_global.buscar("honda", MOTOS, CLIENTES, CONTRATOS)
    assert [m["id"] for m in r["veiculos"]] == ["m1"]
    assert all(c["id"] != "c3" for c in busca_global.buscar("joana", MOTOS, CLIENTES, CONTRATOS)["clientes"])


def test_contratos_pelo_cliente_ou_pelo_veiculo_com_ativo_primeiro():
    r = busca_global.buscar("joana", MOTOS, CLIENTES, CONTRATOS)
    assert [i["contrato"]["id"] for i in r["contratos"]] == ["k2", "k1"]
    assert r["contratos"][0]["cliente"]["id"] == "c1" and r["contratos"][0]["moto"]["id"] == "m1"
    assert [i["contrato"]["id"] for i in busca_global.buscar("factor", MOTOS, CLIENTES, CONTRATOS)["contratos"]] == ["k3"]


def test_limite_por_grupo_e_total():
    muitas = [{"id": f"m{i}", "placa": f"AAA{i}B00", "marca": "Honda", "modelo": "CG", "status": "disponivel"} for i in range(9)]
    r = busca_global.buscar("honda", muitas, [], [])
    assert len(r["veiculos"]) == busca_global.LIMITE_POR_GRUPO == r["total"]


def test_termo_e_normalizado_e_limitado():
    assert busca_global.normalizar_termo("  ab   cd ") == "ab cd"
    assert len(busca_global.normalizar_termo("x" * 500)) == busca_global.TAMANHO_MAXIMO_TERMO
