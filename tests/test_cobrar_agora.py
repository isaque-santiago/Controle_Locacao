"""Aba Hoje do Dashboard: cobrar agora e atenção financeira."""

from datetime import date
from decimal import Decimal

from src.domain import cobrar_agora as c

HOJE = date(2026, 11, 10)
MULTA, DIARIO = Decimal("15"), Decimal("7")


def _cobranca(id="k1", contrato="c1", cliente="cl1", moto="m1", tipo="locacao", saldo="100", vencimento="2026-11-01", situacao="atrasada"):
    return {"id": id, "contrato_id": contrato, "cliente_id": cliente, "moto_id": moto, "tipo": tipo, "saldo": saldo,
            "vencimento": vencimento, "situacao": situacao}


def _analisar(cobrancas, **extra):
    return c.analisar_cobranca(cobrancas, {"cl1": "JOSE", "cl2": "ANA", "cl3": "LUIZ"}, {"m1": "POU7015", "m2": "OSL8828", "m3": "PMP2B63"},
                               MULTA, DIARIO, HOJE, **extra)


def test_um_contrato_soma_debito_encargos_e_usa_o_maior_atraso_e_a_cobranca_mais_antiga():
    r = _analisar([_cobranca("novo", saldo="50", vencimento="2026-11-08"), _cobranca("antigo", saldo="100", vencimento="2026-11-03")])
    linha = r["linhas"][0]
    # 7 dias: 15 + 49 = 64; 2 dias: 15 + 14 = 29
    assert (linha["cliente"], linha["placa"], linha["dias_atraso"], linha["faixa"]) == ("JOSE", "POU7015", 7, "em_atraso")
    assert linha["debito"] == Decimal("150") and linha["encargos"] == Decimal("93.00") and linha["total"] == Decimal("243.00")
    assert linha["cobranca_id"] == "antigo"
    assert r["em_atraso"] == Decimal("150") and r["a_cobrar"] == Decimal("150") and r["vencem_hoje"] == Decimal("0")


def test_o_que_vence_hoje_entra_com_a_multa_do_dia_e_faixa_hoje():
    r = _analisar([_cobranca("h", saldo="280", vencimento="2026-11-10", situacao="aberta")])
    linha = r["linhas"][0]
    assert linha["faixa"] == "hoje" and linha["dias_atraso"] == 0 and linha["hoje"] == Decimal("280") and linha["debito"] == Decimal("0")
    assert linha["encargos"] == Decimal("15.00") and linha["total"] == Decimal("295.00") and linha["cobranca_id"] == "h"
    assert r["a_cobrar"] == Decimal("280") and r["vencem_hoje"] == Decimal("280") and r["contratos_so_hoje"] == 1


def test_contrato_com_atraso_e_vencimento_hoje_tem_uma_linha_so():
    r = _analisar([_cobranca("a", saldo="100", vencimento="2026-11-03"), _cobranca("b", saldo="280", vencimento="2026-11-10", situacao="aberta")])
    assert r["total_linhas"] == 1 and r["linhas"][0]["debito"] == Decimal("100") and r["linhas"][0]["hoje"] == Decimal("280")
    assert r["linhas"][0]["faixa"] == "em_atraso" and r["a_cobrar"] == Decimal("380")
    assert r["linhas"][0]["cobranca_id"] == "a"


def test_ignora_pagas_canceladas_sem_saldo_e_o_que_vence_depois_de_hoje():
    r = _analisar([_cobranca(situacao="paga"), _cobranca(situacao="cancelada"), _cobranca(saldo="0"),
                   _cobranca(situacao="aberta", vencimento="2026-11-11"), _cobranca(situacao="aberta", vencimento="2026-11-09")])
    assert r["total_linhas"] == 0 and r["linhas"] == [] and r["a_cobrar"] == Decimal("0.00")


def test_encargos_so_incidem_sobre_locacao():
    r = _analisar([_cobranca(tipo="multa_transito", saldo="200", vencimento="2026-11-01")])
    assert r["em_atraso"] == Decimal("200") and r["encargos"] == Decimal("0.00")


def test_ordem_do_maior_atraso_para_o_menor_e_no_mesmo_atraso_pelo_maior_valor():
    r = _analisar([
        _cobranca("a", contrato="a", cliente="cl1", moto="m1", saldo="100", vencimento="2026-11-05"),
        _cobranca("b", contrato="b", cliente="cl2", moto="m2", saldo="900", vencimento="2026-11-05"),
        _cobranca("c", contrato="c", cliente="cl3", moto="m3", saldo="50", vencimento="2026-10-20"),
        _cobranca("d", contrato="d", cliente="cl1", moto="m1", saldo="5000", vencimento="2026-11-10", situacao="aberta"),
    ])
    assert [l["contrato_id"] for l in r["linhas"]] == ["c", "b", "a", "d"]


def test_limite_corta_a_lista_mas_nao_os_totais():
    cobrancas = [_cobranca(f"k{i}", contrato=f"c{i}", cliente="cl1", moto="m1", saldo="10", vencimento="2026-11-05") for i in range(5)]
    r = _analisar(cobrancas, limite=2)
    assert len(r["linhas"]) == 2 and r["total_linhas"] == 5 and r["em_atraso"] == Decimal("50")


def test_contagem_por_faixa_usa_o_corte_configurado():
    cobrancas = [_cobranca("a", contrato="a", vencimento="2026-11-06"), _cobranca("b", contrato="b", vencimento="2026-10-20"),
                 _cobranca("c", contrato="c", vencimento="2026-11-10", situacao="aberta")]
    r = _analisar(cobrancas)
    assert (r["contratos_em_atraso"], r["contratos_inadimplentes"], r["contratos_so_hoje"]) == (1, 1, 1)
    r3 = _analisar(cobrancas, corte=3)  # 4 dias já é inadimplência
    assert (r3["contratos_em_atraso"], r3["contratos_inadimplentes"]) == (0, 2)


def test_nomes_e_placas_desconhecidos_viram_traco():
    r = c.analisar_cobranca([_cobranca(cliente="x", moto="y")], {}, {}, MULTA, DIARIO, HOJE)
    assert r["linhas"][0]["cliente"] == "—" and r["linhas"][0]["placa"] == "—"


def test_parcelas_de_divida_atrasadas():
    r = c.parcelas_de_divida_atrasadas([
        {"situacao": "atrasada", "saldo": "1000"}, {"situacao": "atrasada", "saldo": "250.50"}, {"situacao": "a_vencer", "saldo": "9"}, {"situacao": "paga"}])
    assert r == {"quantidade": 2, "valor": Decimal("1250.50")}
    assert c.parcelas_de_divida_atrasadas([]) == {"quantidade": 0, "valor": Decimal("0.00")}


def test_atencao_financeira_lista_so_o_que_existe():
    itens = c.atencao_financeira({"quantidade": 2, "valor": Decimal("1250.50")}, Decimal("40"), Decimal("75"))
    assert [i.titulo for i in itens] == ["Parcela de dívida atrasada", "Despesa a repassar ao locatário", "Entrada do mês sem conta"]
    assert itens[0].quantidade == 2 and itens[0].tom == "perigo" and itens[0].area == "dividas" and itens[0].descricao == "R$ 1.250,50 em atraso"
    assert itens[1].quantidade is None and itens[1].area is None and itens[1].descricao == "R$ 40,00" and itens[1].tom == "atencao"
    assert c.atencao_financeira({"quantidade": 0, "valor": Decimal("0")}, 0, Decimal("0")) == []


def test_ordenar_atencao_poe_o_perigo_na_frente_sem_trocar_a_ordem_dentro_do_grupo():
    from src.domain.painel import ItemAlerta

    itens = [ItemAlerta(1, "A", "", "atencao", "x"), ItemAlerta(2, "B", "", "perigo", "x"), ItemAlerta(3, "C", "", "atencao", None),
             ItemAlerta(4, "D", "", "perigo", None)]
    assert [i.titulo for i in c.ordenar_atencao(itens)] == ["B", "D", "A", "C"]
    assert c.ordenar_atencao([]) == []
