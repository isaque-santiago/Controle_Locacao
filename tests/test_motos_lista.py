"""Regras da lista e da ficha de motos (src/domain/motos_lista.py)."""

from datetime import date

from src.domain import motos_lista as ml

MOTOS = [
    {"id": "1", "placa": "ABC1D23", "marca": "Honda", "modelo": "CG 160", "status": "alugada"},
    {"id": "2", "placa": "XYZ9K87", "marca": "Yamaha", "modelo": "Factor", "status": "disponivel"},
    {"id": "3", "placa": "QRS4T21", "marca": "Honda", "modelo": "Biz", "status": "inativa"},
]


def test_situacao_valida_aceita_status_conhecido_e_cai_em_todas():
    assert ml.situacao_valida("alugada") == "alugada"
    assert ml.situacao_valida("ALUGADA ") == "alugada"
    assert ml.situacao_valida("qualquer") == "todas"
    assert ml.situacao_valida(None) == "todas"


def test_aba_valida_cai_na_primeira():
    assert ml.aba_valida("financeiro") == "financeiro"
    assert ml.aba_valida("../x") == "resumo"
    assert ml.aba_valida(None) == "resumo"


def test_contagem_por_status():
    assert ml.contagem_por_status(MOTOS) == {
        "todas": 3, "disponivel": 1, "alugada": 1, "manutencao": 0, "inativa": 1,
    }


def test_filtra_por_situacao():
    assert [m["id"] for m in ml.filtrar_motos(MOTOS, "inativa")] == ["3"]
    assert len(ml.filtrar_motos(MOTOS, "todas")) == 3


def test_busca_por_placa_com_ou_sem_hifen_e_sem_diferenciar_caixa():
    assert [m["id"] for m in ml.filtrar_motos(MOTOS, busca="abc-1d23")] == ["1"]
    assert [m["id"] for m in ml.filtrar_motos(MOTOS, busca="abc1d")] == ["1"]


def test_busca_por_modelo_marca_e_locatario():
    assert [m["id"] for m in ml.filtrar_motos(MOTOS, busca="honda")] == ["1", "3"]
    assert [m["id"] for m in ml.filtrar_motos(MOTOS, busca="factor")] == ["2"]
    assert [m["id"] for m in ml.filtrar_motos(MOTOS, busca="joana", locatarios={"1": "Joana Prado"})] == ["1"]


def test_busca_e_situacao_combinadas():
    assert ml.filtrar_motos(MOTOS, "disponivel", "honda") == []


def test_busca_so_com_espacos_nao_filtra():
    assert len(ml.filtrar_motos(MOTOS, busca="   ")) == 3


def test_proxima_manutencao_sem_plano():
    r = ml.proxima_manutencao([])
    assert (r.texto, r.situacao) == ("—", "sem_plano")


def test_proxima_manutencao_escolhe_o_item_mais_urgente():
    linhas = [
        {"situacao": "em_dia", "km_restantes": 2000, "dias_restantes": 90},
        {"situacao": "proxima", "km_restantes": 580, "dias_restantes": None},
        {"situacao": "proxima", "km_restantes": 95, "dias_restantes": None},
    ]
    r = ml.proxima_manutencao(linhas)
    assert (r.texto, r.situacao) == ("em 95 km", "proxima")


def test_proxima_manutencao_vencida_por_km_e_por_dias():
    r = ml.proxima_manutencao([{"situacao": "vencida", "km_restantes": -120, "dias_restantes": None}])
    assert (r.texto, r.situacao) == ("vencida há 120 km", "vencida")
    r = ml.proxima_manutencao([{"situacao": "vencida", "km_restantes": None, "dias_restantes": -3}])
    assert r.texto == "vencida há 3 dias"


def test_vencida_ganha_de_proxima_mesmo_com_menos_km():
    linhas = [
        {"situacao": "proxima", "km_restantes": 10, "dias_restantes": None},
        {"situacao": "vencida", "km_restantes": -500, "dias_restantes": None},
    ]
    assert ml.proxima_manutencao(linhas).situacao == "vencida"


def test_proxima_manutencao_milhar_com_ponto_e_so_por_dias():
    r = ml.proxima_manutencao([{"situacao": "em_dia", "km_restantes": 1500, "dias_restantes": 40}])
    assert r.texto == "em 1.500 km"
    r = ml.proxima_manutencao([{"situacao": "em_dia", "km_restantes": None, "dias_restantes": 40}])
    assert r.texto == "em 40 dias"


def test_situacao_do_documento():
    hoje = date(2026, 10, 6)
    assert ml.situacao_documento({"regularizado": True, "vencimento": "2020-01-01"}, hoje) == ("ok", "Em dia")
    assert ml.situacao_documento({"regularizado": False, "vencimento": "2026-10-05"}, hoje) == ("vencido", "Vencido")
    assert ml.situacao_documento({"regularizado": False, "vencimento": "2026-10-06"}, hoje) == ("a_vencer", "A vencer")
