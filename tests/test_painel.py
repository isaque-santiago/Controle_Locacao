"""Regras do Dashboard (src/domain/painel.py)."""

from datetime import date
from decimal import Decimal

from src.domain import painel

HOJE = date(2026, 10, 6)


def _frota(**qtd):
    return [{"status": s} for s, n in qtd.items() for _ in range(n)]


def test_data_por_extenso():
    assert painel.data_por_extenso(HOJE) == "terça-feira, 6 de outubro de 2026"
    assert painel.data_por_extenso(date(2027, 3, 7)) == "domingo, 7 de março de 2027"


def test_contagem_inclui_todos_os_status_mesmo_com_zero():
    contagem = painel.contar_por_status(_frota(alugada=3, disponivel=1))
    assert contagem == {"alugada": 3, "disponivel": 1, "manutencao": 0, "inativa": 0}


def test_ocupacao_ignora_motos_inativas():
    contagem = painel.contar_por_status(_frota(alugada=3, disponivel=1, inativa=4))
    assert painel.percentual_ocupacao(contagem) == 75


def test_ocupacao_sem_motos_ativas_e_zero():
    assert painel.percentual_ocupacao(painel.contar_por_status(_frota(inativa=2))) == 0
    assert painel.percentual_ocupacao(painel.contar_por_status([])) == 0


def test_segmentos_e_descricao_do_medidor():
    contagem = painel.contar_por_status(_frota(alugada=18, disponivel=3, manutencao=3))
    assert [s.status for s in painel.segmentos_frota(contagem)] == list(painel.STATUS_FROTA)
    assert painel.segmentos_frota(contagem)[0].rotulo == "18 alugadas"
    assert painel.descricao_medidor(contagem) == (
        "Frota de 24 motos: 18 alugadas, 3 disponíveis, 3 em manutenção, 0 inativas"
    )


def test_percentual_recebido_limita_entre_0_e_100():
    assert painel.percentual_recebido(Decimal("500"), Decimal("1000")) == 50
    assert painel.percentual_recebido(Decimal("1500"), Decimal("1000")) == 100
    assert painel.percentual_recebido(Decimal("100"), Decimal("0")) == 0


def test_cobrancas_de_hoje_pega_atrasadas_e_abertas_de_hoje_em_ordem():
    cobrancas = [
        {"id": "a", "situacao": "aberta", "vencimento": "2026-10-06"},
        {"id": "b", "situacao": "atrasada", "vencimento": "2026-10-01"},
        {"id": "c", "situacao": "aberta", "vencimento": "2026-10-07"},
        {"id": "d", "situacao": "paga", "vencimento": "2026-10-06"},
        {"id": "e", "situacao": "atrasada", "vencimento": "2026-09-20"},
    ]
    assert [c["id"] for c in painel.cobrancas_de_hoje(cobrancas, HOJE)] == ["e", "b", "a"]


def test_dias_em_atraso_nunca_e_negativo():
    assert painel.dias_em_atraso("2026-10-01", HOJE) == 5
    assert painel.dias_em_atraso("2026-10-09", HOJE) == 0


def test_ordens_concluidas_so_do_mes_atual():
    ordens = [
        {"status": "concluida", "data_entrada": "2026-10-02"},
        {"status": "concluida", "data_entrada": "2026-09-30"},
        {"status": "aberta", "data_entrada": "2026-10-03"},
    ]
    assert painel.ordens_concluidas_no_mes(ordens, HOJE) == 1


CONFIG = {"alerta_manutencao_km": 200, "alerta_manutencao_dias": 15, "alerta_documento_dias": 30}


def test_sem_alertas_devolve_lista_vazia():
    assert painel.agrupar_alertas(CONFIG, [], [], []) == []


def test_alerta_de_manutencao_vencida_lista_ate_dois_itens_distintos():
    manut = [
        {"situacao": "vencida", "item": "Óleo"},
        {"situacao": "vencida", "item": "Óleo"},
        {"situacao": "vencida", "item": "Corrente"},
        {"situacao": "vencida", "item": "Pneu"},
    ]
    (item,) = painel.agrupar_alertas(CONFIG, manut, [], [])
    assert (item.quantidade, item.titulo, item.tom, item.area) == (4, "Manutenção vencida", "perigo", "manutencao")
    assert item.descricao == "Óleo, Corrente e mais 1"


def test_alerta_de_manutencao_proxima_usa_a_configuracao():
    (item,) = painel.agrupar_alertas(CONFIG, [{"situacao": "proxima", "item": "Óleo"}], [], [])
    assert item.descricao == "nos próximos 200 km ou 15 dias"
    assert item.tom == "atencao"


def test_alertas_de_documento_e_cnh():
    docs = [
        {"situacao": "vencido", "tipo": "crlv", "placa": "ABC1D23"},
        {"situacao": "vencido", "tipo": "seguro", "placa": "XYZ9K87"},
        {"situacao": "a_vencer", "tipo": "ipva", "placa": "ABC1D23"},
    ]
    cnh = [{"situacao": "vencida", "nome": "Ana", "cnh_validade": "2026-09-01"}]
    itens = painel.agrupar_alertas(CONFIG, [], docs, cnh)
    assert [i.titulo for i in itens] == ["Documento vencido", "Documento a vencer", "CNH vencida"]
    assert itens[0].descricao == "CRLV · moto ABC1D23 e mais 1"
    assert itens[1].descricao == "próximos 30 dias"
    assert itens[2].descricao == "Ana · 01/09/2026"
    assert itens[2].area == "clientes"
