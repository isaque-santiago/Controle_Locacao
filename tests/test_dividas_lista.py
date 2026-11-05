"""Página Dívidas: saldo em aberto, próxima parcela, situação e totais."""

from datetime import date
from decimal import Decimal

from src.domain import dividas_lista as d


def _saldo(id, credor="Credor", tipo="emprestimo", calculado="1000", confirmado=None, pago="0", original="1000", moto=None):
    return {"divida_id": id, "credor": credor, "tipo": tipo, "saldo_calculado": calculado, "saldo_confirmado": confirmado,
            "total_pago": pago, "valor_original": original, "moto_id": moto}


def _parcela(divida, venc, valor="100", situacao="a_vencer", numero=1):
    return {"divida_id": divida, "vencimento": venc, "valor": valor, "situacao": situacao, "numero": numero}


def test_saldo_em_aberto_prefere_o_confirmado_e_nunca_e_negativo():
    assert d.saldo_em_aberto({"saldo_calculado": "5600", "saldo_confirmado": "3425"}) == Decimal("3425")
    assert d.saldo_em_aberto({"saldo_calculado": "5600", "saldo_confirmado": None}) == Decimal("5600")
    assert d.saldo_em_aberto({"saldo_calculado": "-50", "saldo_confirmado": None}) == Decimal("0.00")
    assert d.saldo_em_aberto({"saldo_calculado": "10", "saldo_confirmado": "0"}) == Decimal("0")


def test_situacao_da_divida():
    assert d.situacao_da_divida(Decimal("0"), 0) == "quitada"
    assert d.situacao_da_divida(Decimal("10"), 0) == "em_aberto"
    assert d.situacao_da_divida(Decimal("10"), 2) == "atrasada"
    assert d.situacao_da_divida(Decimal("0"), 2) == "quitada"


def test_linha_traz_a_proxima_parcela_em_aberto_e_as_atrasadas():
    linhas = d.linhas_da_lista(
        [_saldo("a", calculado="2000")],
        [_parcela("a", "2026-09-28", situacao="paga"), _parcela("a", "2026-10-28", situacao="atrasada", numero=2),
         _parcela("a", "2026-12-28", situacao="a_vencer", numero=4), _parcela("a", "2026-11-28", situacao="a_vencer", numero=3)],
    )
    linha = linhas[0]
    assert linha["proxima_vencimento"] == date(2026, 10, 28) and linha["proxima_valor"] == Decimal("100")
    assert linha["parcelas_abertas"] == 3 and linha["parcelas_atrasadas"] == 1 and linha["situacao"] == "atrasada"
    assert linha["tipo_rotulo"] == "Empréstimo" and linha["saldo"] == Decimal("2000")


def test_divida_sem_parcelas_nao_tem_proxima():
    linha = d.linhas_da_lista([_saldo("a", tipo="moto_fiado")], [])[0]
    assert linha["proxima_vencimento"] is None and linha["parcelas_abertas"] == 0 and linha["situacao"] == "em_aberto"
    assert linha["tipo_rotulo"] == "Moto fiado"


def test_parcela_sem_data_so_vale_se_nao_houver_com_data():
    sem = _parcela("a", None, situacao="sem_data")
    com = _parcela("a", "2026-12-01")
    assert d.linhas_da_lista([_saldo("a")], [sem, com])[0]["proxima_vencimento"] == date(2026, 12, 1)
    assert d.linhas_da_lista([_saldo("a")], [sem])[0]["proxima_vencimento"] is None


def test_ordem_atrasadas_depois_em_aberto_por_saldo_e_quitadas_no_fim():
    saldos = [_saldo("q", "Quitada", calculado="0"), _saldo("g", "Grande", calculado="9000"),
              _saldo("p", "Pequena", calculado="100"), _saldo("t", "Atrasada", calculado="50")]
    parcelas = [_parcela("t", "2026-10-01", situacao="atrasada")]
    assert [l["credor"] for l in d.linhas_da_lista(saldos, parcelas)] == ["Atrasada", "Grande", "Pequena", "Quitada"]


def test_totais_ignoram_quitadas_e_pegam_o_vencimento_mais_proximo():
    saldos = [_saldo("a", "A", tipo="moto_fiado", calculado="3000"), _saldo("b", "B", calculado="500"),
              _saldo("c", "C", calculado="0")]
    parcelas = [_parcela("a", "2026-12-10"), _parcela("b", "2026-11-20"), _parcela("b", "2026-10-01", situacao="atrasada")]
    t = d.totais(d.linhas_da_lista(saldos, parcelas))
    assert t["total_em_aberto"] == Decimal("3500") and t["moto_fiado"] == Decimal("3000")
    assert t["dividas_em_aberto"] == 2 and t["parcelas_atrasadas"] == 1
    assert t["proximo_vencimento"] == date(2026, 10, 1) and t["proximo_credor"] == "B"


def test_totais_sem_dividas():
    t = d.totais([])
    assert t["total_em_aberto"] == Decimal("0.00") and t["proximo_vencimento"] is None


# ---------------------------------------------------------------- limite do pagamento --

_PARCELAS = [
    {"vencimento_id": "v1", "valor": "1000.00", "valor_pago": "1000.00"},
    {"vencimento_id": "v2", "valor": "1000.00", "valor_pago": "400.00"},
]


def test_limite_de_pagamento_de_parcela_e_o_valor_da_parcela_menos_o_que_os_outros_cobriram():
    # a parcela v2 tem R$ 400 pagos, e este pagamento é de R$ 150 desses 400: os outros cobriram 250
    assert d.limite_do_pagamento({"vencimento_id": "v2", "valor": "150"}, _PARCELAS, "9999") == Decimal("750.00")
    assert d.limite_do_pagamento({"vencimento_id": "v1", "valor": "1000"}, _PARCELAS, "0") == Decimal("1000.00")


def test_limite_de_pagamento_direto_e_o_saldo_mais_o_proprio_valor():
    assert d.limite_do_pagamento({"vencimento_id": None, "valor": "300"}, _PARCELAS, "7600") == Decimal("7900")
    assert d.limite_do_pagamento({"valor": "300"}, [], Decimal("0")) == Decimal("300")


def test_limite_com_parcela_desconhecida_cai_no_saldo_da_divida():
    assert d.limite_do_pagamento({"vencimento_id": "x", "valor": "10"}, _PARCELAS, "90") == Decimal("100")
