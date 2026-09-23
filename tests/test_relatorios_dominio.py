from datetime import date
from decimal import Decimal

from src.domain.relatorios import (
    agrupar_por_modelo,
    analisar_inadimplencia,
    previsto_do_mes,
    proporcoes,
)
from src.ui.formatadores import formatar_mes

CONFIG = {
    "multa_atraso_percentual": 2,
    "juros_mensal_percentual": 1,
    "carencia_dias": 0,
}


def test_proporcoes_relativas_ao_maior_e_sem_barra_para_negativos():
    valores = [Decimal("200"), Decimal("100"), Decimal("0"), Decimal("-50")]
    assert proporcoes(valores) == [100, 50, 0, 0]
    assert proporcoes([Decimal("0"), Decimal("0")]) == [0, 0]
    assert proporcoes([]) == []


def test_agrupar_por_modelo_soma_e_media_por_moto():
    resultado = [
        {"modelo": "CG 160", "custo_manutencao": Decimal("100.00")},
        {"modelo": "CG 160", "custo_manutencao": Decimal("50.01")},
        {"modelo": "Biz", "custo_manutencao": Decimal("300.00")},
    ]
    linhas = agrupar_por_modelo(resultado)
    assert [l["modelo"] for l in linhas] == ["Biz", "CG 160"]
    cg = linhas[1]
    assert cg["motos"] == 2
    assert cg["custo_total"] == Decimal("150.01")
    assert cg["custo_medio"] == Decimal("75.01")


def _cobranca(id, vencimento, situacao="aberta", tipo="locacao", saldo="100", valor="100", cliente="c1"):
    return {
        "id": id,
        "tipo": tipo,
        "vencimento": vencimento,
        "situacao": situacao,
        "saldo": saldo,
        "valor": valor,
        "cliente_id": cliente,
        "moto_id": "m1",
    }


def test_previsto_do_mes_ignora_caucao_cancelada_e_outros_meses():
    cobrancas = [
        _cobranca("a", "2026-09-05", valor="100"),
        _cobranca("b", "2026-09-20", valor="50.50", situacao="paga"),
        _cobranca("c", "2026-09-10", tipo="caucao", valor="500"),
        _cobranca("d", "2026-09-11", situacao="cancelada", valor="70"),
        _cobranca("e", "2026-08-31", valor="999"),
    ]
    assert previsto_do_mes(cobrancas, date(2026, 9, 23)) == Decimal("150.50")


def test_inadimplencia_total_percentual_clientes_e_encargos():
    cobrancas = [
        _cobranca("a", "2026-09-13", situacao="atrasada", saldo="100.00", valor="100.00"),
        _cobranca("b", "2026-09-17", situacao="atrasada", saldo="300.00", valor="300.00", cliente="c2"),
        _cobranca("c", "2026-09-30", valor="600.00"),
        _cobranca("d", "2026-09-01", situacao="paga", valor="100.00", saldo="0"),
    ]
    resultado = analisar_inadimplencia(
        cobrancas,
        [{"id": "c1", "nome": "Ana"}, {"id": "c2", "nome": "Bia"}],
        [{"id": "m1", "placa": "ABC1D23"}],
        CONFIG,
        date(2026, 9, 23),
    )
    assert resultado["total_atraso"] == Decimal("400.00")
    assert resultado["clientes"] == 2
    # previsto do mês = 100 + 300 + 600 + 100 = 1100 -> 400 / 1100 = 36,4%
    assert resultado["percentual_carteira"] == Decimal("36.4")
    primeira, segunda = resultado["linhas"]
    assert (primeira["cliente"], primeira["dias_atraso"]) == ("Ana", 10)
    assert primeira["placa"] == "ABC1D23"
    # 100 + multa 2,00 + juros 100 * 1% / 30 * 10 = 0,33
    assert primeira["total_com_encargos"] == Decimal("102.33")
    assert segunda["dias_atraso"] == 6


def test_inadimplencia_sem_carteira_nao_divide_por_zero():
    resultado = analisar_inadimplencia([], [], [], CONFIG, date(2026, 9, 23))
    assert resultado["linhas"] == []
    assert resultado["total_atraso"] == Decimal(0)
    assert resultado["percentual_carteira"] is None


def test_formatar_mes():
    assert formatar_mes("2026-09") == "Setembro de 2026"
    assert formatar_mes(date(2026, 3, 1)) == "Março de 2026"
