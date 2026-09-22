"""Formatação de moeda (R$), data (dd/mm/aaaa), placa e CPF mascarado."""


def formatar_moeda(valor) -> str:
    from decimal import Decimal

    numero = f"{Decimal(str(valor or 0)):,.2f}"
    return "R$ " + numero.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_compacta(valor) -> str:
    """R$ sem centavos, para leituras grandes tipo odômetro (painel do Dashboard)."""
    from decimal import Decimal, ROUND_HALF_UP

    numero = Decimal(str(valor or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    texto = f"{numero:,}".replace(",", ".")
    return "R$ " + texto


def formatar_data(data) -> str:
    from datetime import date, datetime

    if not data:
        return "—"
    if isinstance(data, (date, datetime)):
        return data.strftime("%d/%m/%Y")
    return date.fromisoformat(str(data)[:10]).strftime("%d/%m/%Y")


def formatar_placa(placa: str) -> str:
    placa = placa.upper().replace("-", "")
    return placa[:3] + "-" + placa[3:] if len(placa) == 7 else placa


def mascarar_cpf(cpf: str) -> str:
    digitos = "".join(c for c in cpf if c.isdigit())
    return "***." + digitos[3:6] + ".***-**" if len(digitos) == 11 else "***"
