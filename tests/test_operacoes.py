"""Chave de operação (Etapa 7): mesmo envio, mesma chave; envio diferente, chave nova."""

from datetime import date
from decimal import Decimal

from src.domain.operacoes import chave_para, impressao


def _sequencia():
    contador = iter(range(1, 100))
    return lambda: f"chave-{next(contador)}"


def test_impressao_e_estavel_e_distingue_conteudo():
    base = {"cobranca": "c1", "data": date(2026, 10, 2), "valor": Decimal("450.00")}
    assert impressao(base) == impressao(dict(reversed(list(base.items()))))
    assert impressao(base) != impressao({**base, "valor": Decimal("450.01")})
    assert impressao([1, "a"]) != impressao(["a", 1])


def test_mesmo_conteudo_reaproveita_a_chave():
    nova = _sequencia()
    primeira = chave_para(None, {"valor": "10"}, nova)
    repetida = chave_para(primeira, {"valor": "10"}, nova)
    assert repetida == primeira
    assert primeira[1] == "chave-1"


def test_conteudo_diferente_ganha_chave_nova():
    nova = _sequencia()
    primeira = chave_para(None, {"valor": "10"}, nova)
    segunda = chave_para(primeira, {"valor": "20"}, nova)
    assert segunda[1] == "chave-2" and segunda[0] != primeira[0]
