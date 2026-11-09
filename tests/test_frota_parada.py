"""Aba Frota: motos paradas, tempo parado e receita por moto."""

from datetime import date
from decimal import Decimal

from src.domain import frota_parada as f

HOJE = date(2026, 11, 10)


def _moto(id, status, placa=None):
    return {"id": id, "status": status, "placa": placa or id.upper()}


def test_motos_paradas_em_manutencao_contam_desde_a_ordem_aberta_mais_antiga():
    motos = [_moto("m1", "manutencao", "POT5B25")]
    ordens = [{"moto_id": "m1", "status": "aberta", "data_entrada": "2026-11-08"}, {"moto_id": "m1", "status": "aberta", "data_entrada": "2026-11-02"},
              {"moto_id": "m1", "status": "concluida", "data_entrada": "2026-10-01"}]
    r = f.motos_paradas(motos, [], ordens, HOJE)
    assert r["linhas"] == [{"moto_id": "m1", "placa": "POT5B25", "motivo": "Em manutenção", "desde": date(2026, 11, 2), "dias": 8}] and r["total"] == 1


def test_motos_disponiveis_contam_desde_o_ultimo_contrato_encerrado_e_sem_contrato_ficam_sem_data():
    motos = [_moto("a", "disponivel"), _moto("b", "disponivel"), _moto("c", "disponivel")]
    contratos = [{"moto_id": "a", "status": "encerrado", "data_encerramento": "2026-10-01"}, {"moto_id": "a", "status": "encerrado", "data_encerramento": "2026-10-20"},
                 {"moto_id": "a", "status": "ativo", "data_encerramento": None}, {"moto_id": "b", "status": "cancelado", "data_encerramento": "2026-09-01"}]
    r = f.motos_paradas(motos, contratos, [], HOJE)
    assert [(l["moto_id"], l["dias"]) for l in r["linhas"]] == [("a", 21), ("b", None), ("c", None)] and r["linhas"][1]["desde"] is None


def test_motos_alugadas_e_inativas_nao_estao_paradas_e_a_lista_vai_do_mais_parado_ao_menos():
    motos = [_moto("a", "alugada"), _moto("i", "inativa"), _moto("x", "manutencao"), _moto("y", "manutencao")]
    ordens = [{"moto_id": "x", "status": "aberta", "data_entrada": "2026-11-09"}, {"moto_id": "y", "status": "aberta", "data_entrada": "2026-10-20"}]
    r = f.motos_paradas(motos, [], ordens, HOJE)
    assert [l["moto_id"] for l in r["linhas"]] == ["y", "x"]


def test_limite_corta_a_lista_mas_o_total_continua():
    motos = [_moto(f"m{i}", "disponivel") for i in range(5)]
    r = f.motos_paradas(motos, [], [], HOJE, limite=2)
    assert len(r["linhas"]) == 2 and r["total"] == 5


def test_tempo_parado_soma_dias_na_oficina_dentro_do_mes_ate_hoje():
    # mês corrente, 10 dias decorridos, 20 motos ativas: base = 200 moto-dias
    ordens = [
        {"status": "aberta", "data_entrada": "2026-11-08", "data_saida": None},        # 8 a 10 = 3 dias
        {"status": "concluida", "data_entrada": "2026-10-28", "data_saida": "2026-11-02"},  # 1 a 2 = 2 dias (o resto é de outubro)
        {"status": "concluida", "data_entrada": "2026-11-05", "data_saida": "2026-11-05"},  # 1 dia
        {"status": "cancelada", "data_entrada": "2026-11-01", "data_saida": "2026-11-09"},  # não conta
        {"status": "concluida", "data_entrada": "2026-10-01", "data_saida": "2026-10-15"},  # fora do mês
    ]
    r = f.tempo_parado_no_mes(ordens, 20, date(2026, 11, 1), HOJE)
    assert r == {"dias": 6, "percentual": Decimal("3.0")}


def test_tempo_parado_de_mes_fechado_usa_o_mes_inteiro_e_sem_motos_nao_tem_percentual():
    ordens = [{"status": "concluida", "data_entrada": "2026-09-10", "data_saida": "2026-09-19"}]
    assert f.tempo_parado_no_mes(ordens, 10, date(2026, 9, 1), HOJE) == {"dias": 10, "percentual": Decimal("3.3")}  # 10 de 300
    assert f.tempo_parado_no_mes(ordens, 0, date(2026, 9, 1), HOJE)["percentual"] is None


def test_receita_por_moto():
    assert f.receita_por_moto(Decimal("1128"), 34) == Decimal("33.18")
    assert f.receita_por_moto(None, 5) == Decimal("0.00") and f.receita_por_moto(100, 0) is None
