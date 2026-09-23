"""Regras de exibição da página Cobranças (abas, resumo de atraso, mensagem)."""

from datetime import date, timedelta
from decimal import Decimal

ABAS = ("Hoje", "Atrasadas", "Próximos 7 dias", "Pagas")
_ABERTAS = ("aberta", "atrasada")


def pertence_a_aba(situacao: str, vencimento: date, aba: str, hoje: date) -> bool:
    """Diz se uma cobrança aparece na aba: Hoje, Atrasadas, Próximos 7 dias ou Pagas."""
    if aba == "Pagas":
        return situacao == "paga"
    if aba == "Atrasadas":
        return situacao == "atrasada"
    if situacao not in _ABERTAS:
        return False
    if aba == "Hoje":
        return vencimento == hoje
    if aba == "Próximos 7 dias":
        return hoje < vencimento <= hoje + timedelta(days=7)
    raise ValueError(f"Aba desconhecida: {aba}")


def resumo_atraso(cobrancas: list[dict]) -> tuple[Decimal, int]:
    """Total do saldo em atraso e quantidade de clientes distintos atrasados."""
    atrasadas = [c for c in cobrancas if c["situacao"] == "atrasada"]
    total = sum((Decimal(str(c["saldo"])) for c in atrasadas), Decimal("0"))
    return total, len({c["cliente_id"] for c in atrasadas})


def mensagem_cobranca(
    cliente: str, placa: str, vencimento: str, saldo: str, dias_atraso: int = 0
) -> str:
    """Texto pronto para colar no WhatsApp. `vencimento` e `saldo` já formatados."""
    if dias_atraso > 0:
        situacao = f"está em atraso há {dias_atraso} dia(s)"
    else:
        situacao = "vence na data indicada"
    return (
        f"Olá, {cliente}. A cobrança de {vencimento}, referente à moto {placa}, "
        f"{situacao}, com saldo de {saldo} antes dos encargos. "
        "Por favor, entre em contato para regularizar."
    )
