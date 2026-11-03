"""Compra a prazo como dívida (ex.: Celta, entrada de R$ 5.000 + 9 parcelas de R$ 1.000)."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.dividas import calendario_parcelas, saldo_compra, validar_compra_parcelada
from src.repositories import dividas


def criar_compra_parcelada(
    credor: str,
    valor_total: Decimal,
    numero_parcelas: int,
    valor_parcela: Decimal,
    primeira_parcela: date,
    valor_entrada: Decimal = Decimal("0"),
    data_entrada: Optional[date] = None,
    parcelas_pagas: int = 0,
    conta_id: Optional[str] = None,
    fornecedor_id: Optional[str] = None,
    moto_id: Optional[str] = None,
    descricao: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Cria a dívida com a entrada e o calendário de parcelas. As `parcelas_pagas` primeiras entram como pagas
    (data = vencimento, marcada como estimada). A conferência dos números é a mesma da RPC."""
    credor = (credor or "").strip()
    if not credor:
        raise ValueError("Informe o credor da compra parcelada.")
    validar_compra_parcelada(valor_total, valor_entrada, numero_parcelas, valor_parcela, parcelas_pagas)
    payload = {
        "credor": credor,
        "valor_total": str(valor_total),
        "valor_entrada": str(valor_entrada),
        "numero_parcelas": numero_parcelas,
        "valor_parcela": str(valor_parcela),
        "primeira_parcela": primeira_parcela.isoformat(),
        "parcelas_pagas": parcelas_pagas,
        "data_entrada": data_entrada.isoformat() if data_entrada else None,
        "conta_id": conta_id,
        "fornecedor_id": fornecedor_id,
        "moto_id": moto_id,
        "descricao": (descricao or "").strip() or None,
        "observacoes": (observacoes or "").strip() or None,
    }
    return dividas.criar_compra_parcelada(payload)


def previa_calendario(primeira_parcela: date, numero_parcelas: int, valor_parcela: Decimal) -> list:
    """Prévia das parcelas (número, vencimento, valor), igual à que a RPC grava."""
    return [
        {"numero": i + 1, "vencimento": vencimento, "valor": valor_parcela}
        for i, vencimento in enumerate(calendario_parcelas(primeira_parcela, numero_parcelas))
    ]


def previa_saldo(
    valor_total: Decimal, valor_entrada: Decimal, valor_parcela: Decimal, parcelas_pagas: int
) -> Decimal:
    return saldo_compra(valor_total, valor_entrada, valor_parcela, parcelas_pagas)


def pagar_parcela(
    vencimento_id: str,
    data: date,
    valor: Optional[Decimal] = None,
    conta_id: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Paga uma parcela (padrão: o saldo todo). Pagamento parcial é aceito; a parcela só fica 'paga'
    quando a soma cobre o valor."""
    if valor is not None and valor <= 0:
        raise ValueError("O valor do pagamento deve ser positivo.")
    return dividas.pagar_parcela(vencimento_id, data, valor, conta_id, (observacoes or "").strip() or None)


def parcelas_da_divida(divida_id: str) -> list:
    return dividas.listar_parcelas(divida_id)
