"""Regras puras da página Cobranças (src/domain/cobrancas_lista.py)."""

from datetime import date

from src.domain import cobrancas_lista as regras

HOJE = date(2026, 10, 7)


def _c(id_, situacao, vencimento, **extra):
    return {"id": id_, "situacao": situacao, "vencimento": vencimento, **extra}


def test_aba_invalida_ou_ausente_abre_em_hoje():
    assert regras.aba_valida(None) == "hoje"
    assert regras.aba_valida("xyz") == "hoje"
    assert regras.aba_valida("pagas") == "pagas"


def test_classificar_separa_as_quatro_abas():
    linhas = [
        _c("hoje", "aberta", "2026-10-07"),
        _c("atraso", "atrasada", "2026-10-01"),
        _c("prox", "aberta", "2026-10-14"),
        _c("limite", "aberta", "2026-10-15"),
        _c("paga", "paga", "2026-09-01"),
        _c("cancelada", "cancelada", "2026-10-07"),
    ]
    abas = regras.classificar(linhas, HOJE)
    assert [c["id"] for c in abas["hoje"]] == ["hoje"]
    assert [c["id"] for c in abas["atrasadas"]] == ["atraso"]
    assert [c["id"] for c in abas["proximos"]] == ["prox"]  # 15/10 já passa de 7 dias
    assert [c["id"] for c in abas["pagas"]] == ["paga"]


def test_ordenar_pagas_pelo_pagamento_mais_recente_e_demais_pelo_vencimento():
    pagas = [_c("a", "paga", "2026-09-01", pago_em="2026-09-02"), _c("b", "paga", "2026-08-01", pago_em="2026-09-20"),
             _c("c", "paga", "2026-07-01", pago_em=None)]
    assert [c["id"] for c in regras.ordenar("pagas", pagas)] == ["b", "a", "c"]
    abertas = [_c("x", "atrasada", "2026-10-01"), _c("y", "atrasada", "2026-09-01")]
    assert [c["id"] for c in regras.ordenar("atrasadas", abertas)] == ["y", "x"]


def test_montar_pagina_limita_ao_intervalo_valido():
    linhas = [{"id": i} for i in range(23)]
    itens, recorte = regras.montar_pagina(linhas, 3)
    assert len(itens) == 3 and recorte.total == 23 and recorte.total_paginas == 3
    itens, recorte = regras.montar_pagina(linhas, 99)
    assert recorte.pagina == 3 and itens[0]["id"] == 20
    assert regras.montar_pagina([], 1)[1].total == 0
